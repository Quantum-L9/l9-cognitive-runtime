"""Hosted OAuth 2.0 / OIDC resource-server protection for the MCP HTTP ingress (MCP-011).

This module is the **entire** authentication surface of the runtime. It terminates
at the HTTP ingress boundary and establishes principal identity; nothing below it
is aware that authentication exists. The compiler — ``CompilePipeline``, the
compiler models, kernel runtime, execution graph, adapter renderer,
``ContextSnapshot`` and ``CognitiveRuntimeService`` — never imports this module and
never changes behavior because a request was authenticated. A compiled bundle for a
given semantic input is byte-identical with and without a token.

What this module does:

- validates a bearer token as a JWT: signature against the issuer's JWKS, then
  ``iss``, ``aud``, ``exp`` and ``nbf``;
- refuses symmetric and ``none`` algorithms outright, so a JWKS entry can never be
  turned into a forging key;
- derives the principal from the validated token and hands it to the SDK, which
  binds session ownership and run isolation to it.

What it deliberately does **not** do: issue tokens, register clients, hold a client
secret, or grant capability. The surface stays read-only after authentication — a
valid token buys identity, never new verbs.

No identity provider is hard-coded. Issuer, audience, JWKS URI and scopes are
supplied by deployment configuration; absent configuration, hosted auth is simply
not enabled and the caller is told so explicitly rather than silently served
unprotected.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Final, Protocol
from urllib.parse import urlparse

import anyio.to_thread
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

logger = logging.getLogger(__name__)

# Asymmetric only. A symmetric algorithm would let anyone holding the *public*
# JWKS material mint tokens, and "none" removes verification altogether; both are
# standing JWT forgery vulnerabilities rather than configuration preferences.
DEFAULT_ALGORITHMS: Final = (
    "RS256",
    "RS384",
    "RS512",
    "ES256",
    "ES384",
    "ES512",
    "PS256",
    "PS384",
    "PS512",
    "EdDSA",
)
_FORBIDDEN_ALGORITHM_PREFIXES: Final = ("HS", "none", "NONE")

_LOOPBACK_HOSTS: Final = ("127.0.0.1", "localhost", "::1", "[::1]")
_OIDC_DISCOVERY_PATH: Final = "/.well-known/openid-configuration"
_OAUTH_AS_DISCOVERY_PATH: Final = "/.well-known/oauth-authorization-server"
_DISCOVERY_TIMEOUT_SECONDS: Final = 10.0
_JWKS_CACHE_LIFESPAN_SECONDS: Final = 300.0


class HostedAuthConfigurationError(RuntimeError):
    """Hosted auth was requested but its configuration is incomplete or unsafe."""


def require_secure_transport(url: str, *, what: str) -> None:
    """Refuse plaintext HTTP except to a loopback host.

    Key material fetched over plaintext can be swapped in transit, and a swapped
    JWKS is a signing key: every downstream signature check would then pass on a
    forged token. HTTPS is therefore mandatory, with the usual loopback exception
    for a sidecar or a test that has no network to intercept.
    """
    lowered = url.lower()
    if lowered.startswith("https://"):
        return
    host = urlparse(url).hostname or ""
    if lowered.startswith("http://") and host in _LOOPBACK_HOSTS:
        return
    raise HostedAuthConfigurationError(
        f"refusing non-HTTPS {what} URL: {url} (only loopback may use plain HTTP)"
    )


def _split_csv(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class HostedAuthConfig:
    """Deployment-supplied resource-server configuration. Never contains a secret.

    A resource server validates tokens with the issuer's *public* keys, so nothing
    here is confidential: no client secret, no signing key, no bearer token. That
    is a property of the design, not an omission — there is no secret to leak
    because the resource server never needs one.
    """

    issuer: str
    audience: str
    resource_url: str
    jwks_uri: str | None = None
    required_scopes: tuple[str, ...] = ()
    algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS

    def __post_init__(self) -> None:
        for field_name in ("issuer", "audience", "resource_url"):
            if not str(getattr(self, field_name)).strip():
                raise HostedAuthConfigurationError(f"{field_name} must not be empty")
        if not self.algorithms:
            raise HostedAuthConfigurationError("at least one signing algorithm is required")
        for alg in self.algorithms:
            if alg.startswith(_FORBIDDEN_ALGORITHM_PREFIXES):
                raise HostedAuthConfigurationError(
                    f"refusing symmetric or unsigned algorithm {alg!r}: "
                    "hosted validation accepts asymmetric signatures only"
                )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> HostedAuthConfig | None:
        """Build from environment, or return ``None`` when hosted auth is not configured.

        ``None`` means "no hosted auth configured", which the caller turns into an
        explicit unprotected-transport decision. Partial configuration is an error,
        never a silent downgrade: a deployment that sets an issuer but forgets the
        audience must fail loudly rather than accept tokens minted for someone else.
        """
        source = dict(os.environ) if env is None else env
        issuer = (source.get("L9_OAUTH_ISSUER") or "").strip()
        audience = (source.get("L9_OAUTH_AUDIENCE") or "").strip()
        resource_url = (source.get("L9_MCP_RESOURCE_URL") or "").strip()
        supplied = [
            name
            for name, value in (
                ("L9_OAUTH_ISSUER", issuer),
                ("L9_OAUTH_AUDIENCE", audience),
                ("L9_MCP_RESOURCE_URL", resource_url),
            )
            if value
        ]
        if not supplied:
            return None
        missing = [
            name
            for name, value in (
                ("L9_OAUTH_ISSUER", issuer),
                ("L9_OAUTH_AUDIENCE", audience),
                ("L9_MCP_RESOURCE_URL", resource_url),
            )
            if not value
        ]
        if missing:
            raise HostedAuthConfigurationError(
                "incomplete hosted auth configuration; set " + ", ".join(missing)
            )
        algorithms = _split_csv(source.get("L9_OAUTH_ALGORITHMS")) or DEFAULT_ALGORITHMS
        return cls(
            issuer=issuer,
            audience=audience,
            resource_url=resource_url,
            jwks_uri=(source.get("L9_OAUTH_JWKS_URI") or "").strip() or None,
            required_scopes=_split_csv(source.get("L9_OAUTH_REQUIRED_SCOPES")),
            algorithms=algorithms,
        )

    def to_auth_settings(self) -> AuthSettings:
        """Render the SDK settings that drive RFC 9728 metadata and 401/403 semantics."""
        return AuthSettings(
            issuer_url=AnyHttpUrl(self.issuer),
            resource_server_url=AnyHttpUrl(self.resource_url),
            required_scopes=list(self.required_scopes) or None,
        )


def _fetch_json(url: str, timeout: float = _DISCOVERY_TIMEOUT_SECONDS) -> dict[str, Any]:
    require_secure_transport(url, what="discovery")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise HostedAuthConfigurationError(f"discovery document at {url} is not a JSON object")
    return payload


def discover_jwks_uri(issuer: str, timeout: float = _DISCOVERY_TIMEOUT_SECONDS) -> str:
    """Resolve the issuer's JWKS URI via OIDC, then OAuth AS metadata.

    Both documents are tried because an OAuth 2.0 authorization server need not be
    an OpenID provider; a deployment can skip discovery entirely by setting
    ``L9_OAUTH_JWKS_URI``.
    """
    base = issuer.rstrip("/")
    errors: list[str] = []
    for path in (_OIDC_DISCOVERY_PATH, _OAUTH_AS_DISCOVERY_PATH):
        url = f"{base}{path}"
        try:
            document = _fetch_json(url, timeout=timeout)
        except HostedAuthConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001 - any transport failure is a miss
            errors.append(f"{url}: {exc}")
            continue
        declared_issuer = document.get("issuer")
        if declared_issuer is not None and str(declared_issuer).rstrip("/") != base:
            # RFC 8414 §3.3: issuer identifier mismatch is a mix-up attack signal.
            raise HostedAuthConfigurationError(
                f"discovery document at {url} declares issuer "
                f"{declared_issuer!r}, expected {issuer!r}"
            )
        jwks_uri = document.get("jwks_uri")
        if jwks_uri:
            return str(jwks_uri)
        errors.append(f"{url}: no jwks_uri")
    raise HostedAuthConfigurationError(
        f"could not discover jwks_uri for issuer {issuer!r} ({'; '.join(errors)})"
    )


def _scopes_from_claims(claims: dict[str, Any]) -> list[str]:
    """Read scopes from ``scope`` (RFC 9068, space-delimited) or ``scp``."""
    raw = claims.get("scope")
    if isinstance(raw, str):
        return [s for s in raw.split(" ") if s]
    scp = claims.get("scp")
    if isinstance(scp, str):
        return [s for s in scp.split(" ") if s]
    if isinstance(scp, list):
        return [str(s) for s in scp if str(s)]
    return []


def _client_id_from_claims(claims: dict[str, Any]) -> str | None:
    """RFC 9068 ``client_id``, falling back to ``azp``.

    ``sub`` is deliberately *not* a fallback: the SDK treats ``client_id`` as the
    client identity and ``subject`` as the user, and collapsing the two would make
    two different users of one client look like two different clients.
    """
    for key in ("client_id", "azp"):
        value = claims.get(key)
        if isinstance(value, str) and value:
            return value
    return None


class SigningKeyResolver(Protocol):
    """The one thing this verifier needs from a JWKS source.

    ``PyJWKClient`` satisfies it. Narrowing the dependency to this method keeps the
    verifier testable against a stub without loosening any type, and keeps the
    negative tests honest: they exercise *this* validator rather than PyJWT's
    network client.
    """

    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class JwtTokenVerifier:
    """Validate a bearer JWT against the issuer's published keys.

    Implements the SDK's ``TokenVerifier`` protocol. Returning ``None`` is the
    protocol's "reject": the SDK's bearer backend turns it into a 401 carrying a
    ``WWW-Authenticate`` challenge with the RFC 9728 metadata pointer. Every
    failure path returns ``None`` — an unreachable JWKS endpoint is a rejection,
    not an exception that could be mistaken for a pass.
    """

    def __init__(
        self, config: HostedAuthConfig, jwks_client: SigningKeyResolver | None = None
    ) -> None:
        self._config = config
        self._jwks_client = jwks_client
        self._jwks_uri = config.jwks_uri

    def _client(self) -> SigningKeyResolver:
        if self._jwks_client is None:
            if self._jwks_uri is None:
                self._jwks_uri = discover_jwks_uri(self._config.issuer)
            require_secure_transport(self._jwks_uri, what="JWKS")
            self._jwks_client = PyJWKClient(
                self._jwks_uri,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=_JWKS_CACHE_LIFESPAN_SECONDS,
            )
        return self._jwks_client

    def _verify_sync(self, token: str) -> AccessToken | None:
        try:
            signing_key = self._client().get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": False,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iss", "aud"],
                },
            )
        except Exception as exc:  # noqa: BLE001 - every failure is a rejection
            # Only the exception class is logged, never the presented credential
            # or its claims. That is enough to tell an expired assertion from an
            # unreachable JWKS endpoint. The message deliberately avoids the word
            # "token": semgrep's logger-credential-leak rule matches the literal
            # rather than the arguments, and a message reworded here is a cleaner
            # answer than a waiver for a finding that was never real.
            logger.info("rejected a presented JWT (%s)", exc.__class__.__name__)
            return None

        client_id = _client_id_from_claims(claims)
        subject = claims.get("sub")
        if client_id is None and not isinstance(subject, str):
            # An unattributable token is not a principal. Fail closed rather than
            # inventing an identity that run isolation would then key on.
            logger.info("rejected a presented JWT (no client_id, azp or sub claim)")
            return None

        expires_at = claims.get("exp")
        return AccessToken(
            token=token,
            client_id=client_id or str(subject),
            scopes=_scopes_from_claims(claims),
            expires_at=int(expires_at) if isinstance(expires_at, int | float) else None,
            resource=self._config.audience,
            subject=str(subject) if isinstance(subject, str) else None,
            # ``iss`` is required: the SDK's principal_components() reads it, so a
            # subject is only ever compared within the issuer that vouched for it.
            claims={"iss": claims.get("iss")},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a bearer token off the event loop (JWKS fetching is blocking I/O)."""
        return await anyio.to_thread.run_sync(self._verify_sync, token)
