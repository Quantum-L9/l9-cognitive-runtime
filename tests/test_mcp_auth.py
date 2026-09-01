"""Hosted OAuth/OIDC resource-server protection for the MCP HTTP ingress (MCP-011).

The discriminating tests here are the negative ones. A suite that only proves a
good token works cannot tell a real validator from ``return AccessToken(...)``,
so every rejection reason — signature, issuer, audience, expiry, not-before,
algorithm — is exercised separately against a server that accepts the *same*
token when only that one attribute is corrected.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import httpx2 as httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.types import CallToolResult, InputRequiredResult
from starlette.testclient import TestClient

from l9_cognitive_runtime.mcp import LOCAL_PRINCIPAL, build_server
from l9_cognitive_runtime.mcp.auth import (
    DEFAULT_ALGORITHMS,
    HostedAuthConfig,
    HostedAuthConfigurationError,
    JwtTokenVerifier,
    require_secure_transport,
)
from l9_cognitive_runtime.mcp.http import create_http_app, resolve_hosted_auth

ISSUER = "https://issuer.example.com"
AUDIENCE = "https://runtime.example.com/v1/mcp"
RESOURCE_URL = "https://runtime.example.com/v1/mcp"
MISSION = "Audit this repository."


# --- key material and token minting -----------------------------------------


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def other_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _StubJWKClient:
    """Stand in for the issuer's JWKS endpoint, serving one fixed public key."""

    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        self._public = key.public_key()

    def get_signing_key_from_jwt(self, token: str) -> Any:
        return type("_Key", (), {"key": self._public})()


def mint(
    key: rsa.RSAPrivateKey,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    subject: str = "user-a",
    client_id: str = "chatgpt-client",
    scopes: str = "l9.compile",
    expires_in: int = 300,
    not_before: int | None = None,
    algorithm: str = "RS256",
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "client_id": client_id,
        "scope": scopes,
        "iat": now,
        "exp": now + expires_in,
    }
    if not_before is not None:
        claims["nbf"] = not_before
    return jwt.encode(claims, key, algorithm=algorithm)


@pytest.fixture
def config() -> HostedAuthConfig:
    return HostedAuthConfig(issuer=ISSUER, audience=AUDIENCE, resource_url=RESOURCE_URL)


@pytest.fixture
def verifier(config: HostedAuthConfig, signing_key: rsa.RSAPrivateKey) -> JwtTokenVerifier:
    return JwtTokenVerifier(config, jwks_client=_StubJWKClient(signing_key))


def verify(verifier: JwtTokenVerifier, token: str) -> Any:
    return asyncio.run(verifier.verify_token(token))


# --- token validation: one rejection reason at a time ------------------------


def test_valid_token_accepted(verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey) -> None:
    token = verify(verifier, mint(signing_key))
    assert token is not None
    assert token.subject == "user-a"
    assert token.client_id == "chatgpt-client"
    assert token.scopes == ["l9.compile"]
    assert (token.claims or {}).get("iss") == ISSUER


def test_malformed_token_rejected(verifier: JwtTokenVerifier) -> None:
    assert verify(verifier, "not-a-jwt") is None
    assert verify(verifier, "") is None
    assert verify(verifier, "a.b.c") is None


def test_expired_token_rejected(verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey) -> None:
    assert verify(verifier, mint(signing_key, expires_in=-30)) is None


def test_not_yet_valid_token_rejected(
    verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    assert verify(verifier, mint(signing_key, not_before=int(time.time()) + 600)) is None


def test_wrong_issuer_rejected(verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey) -> None:
    assert verify(verifier, mint(signing_key, issuer="https://evil.example.com")) is None


def test_wrong_audience_rejected(
    verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    assert verify(verifier, mint(signing_key, audience="https://someone-else.example")) is None


def test_invalid_signature_rejected(
    verifier: JwtTokenVerifier, other_key: rsa.RSAPrivateKey
) -> None:
    # Signed by a key the issuer never published.
    assert verify(verifier, mint(other_key)) is None


def test_unattributable_token_rejected(
    verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    now = int(time.time())
    token = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300},
        signing_key,
        algorithm="RS256",
    )
    assert verify(verifier, token) is None


def test_symmetric_and_unsigned_algorithms_are_refused_by_configuration() -> None:
    # A symmetric algorithm would let anyone holding the public JWKS material mint
    # tokens; "none" removes verification entirely. Both are refused at config time
    # so a deployment cannot opt into forgery.
    for bad in ("HS256", "none"):
        with pytest.raises(HostedAuthConfigurationError):
            HostedAuthConfig(
                issuer=ISSUER, audience=AUDIENCE, resource_url=RESOURCE_URL, algorithms=(bad,)
            )
    assert all(not alg.startswith(("HS", "none")) for alg in DEFAULT_ALGORITHMS)


def test_algorithm_confusion_token_rejected(
    verifier: JwtTokenVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    # The classic confusion attack: an HS256 token MAC'd with the issuer's *public*
    # RSA material, which a naive verifier would accept as a valid signature.
    # PyJWT refuses to mint it, so it is assembled by hand — the point is to prove
    # our verifier rejects it, not that PyJWT's encoder does.
    public_pem = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    now = int(time.time())

    def segment(payload: dict[str, Any]) -> bytes:
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = b".".join(
        [
            segment({"alg": "HS256", "typ": "JWT"}),
            segment({"iss": ISSUER, "aud": AUDIENCE, "sub": "attacker", "exp": now + 300}),
        ]
    )
    mac = hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    forged = (signing_input + b"." + base64.urlsafe_b64encode(mac).rstrip(b"=")).decode()

    assert verify(verifier, forged) is None


# --- configuration -----------------------------------------------------------


def test_key_material_is_refused_over_plaintext_http() -> None:
    # A swapped JWKS is a signing key: every downstream signature check would then
    # pass on a forged token. Loopback keeps sidecar and test setups workable.
    for insecure in (
        "http://issuer.example.com/jwks",
        "http://10.0.0.5/.well-known/jwks.json",
        "ftp://issuer.example.com/jwks",
    ):
        with pytest.raises(HostedAuthConfigurationError):
            require_secure_transport(insecure, what="JWKS")
    for allowed in (
        "https://issuer.example.com/jwks",
        "http://127.0.0.1:9/jwks",
        "http://localhost:9/jwks",
    ):
        require_secure_transport(allowed, what="JWKS")


def test_a_plaintext_jwks_uri_rejects_every_token(
    config: HostedAuthConfig, signing_key: rsa.RSAPrivateKey
) -> None:
    insecure = HostedAuthConfig(
        issuer=config.issuer,
        audience=config.audience,
        resource_url=config.resource_url,
        jwks_uri="http://issuer.example.com/jwks",
    )
    # No stub client: the verifier must reach for the real URI and refuse it.
    assert verify(JwtTokenVerifier(insecure), mint(signing_key)) is None


def test_partial_configuration_fails_loudly_rather_than_downgrading() -> None:
    with pytest.raises(HostedAuthConfigurationError):
        HostedAuthConfig.from_env({"L9_OAUTH_ISSUER": ISSUER})
    assert HostedAuthConfig.from_env({}) is None


def test_require_auth_refuses_to_start_unprotected() -> None:
    with pytest.raises(HostedAuthConfigurationError):
        resolve_hosted_auth({"L9_REQUIRE_AUTH": "true"})
    assert resolve_hosted_auth({}) == (None, None)


def test_no_credential_material_is_read_from_configuration() -> None:
    # A resource server validates with public keys; it has no secret to hold.
    config = HostedAuthConfig.from_env(
        {
            "L9_OAUTH_ISSUER": ISSUER,
            "L9_OAUTH_AUDIENCE": AUDIENCE,
            "L9_MCP_RESOURCE_URL": RESOURCE_URL,
            "L9_OAUTH_REQUIRED_SCOPES": "l9.compile, l9.read",
        }
    )
    assert config is not None
    assert config.required_scopes == ("l9.compile", "l9.read")
    serialized = json.dumps(config.__dict__, default=str).lower()
    for forbidden in ("secret", "private_key", "password", "client_secret"):
        assert forbidden not in serialized


# --- HTTP ingress: challenge semantics ---------------------------------------


def protected_app(pack: Path, verifier: JwtTokenVerifier, config: HostedAuthConfig) -> Any:
    return create_http_app(pack, token_verifier=verifier, auth_settings=config.to_auth_settings())


def test_missing_token_is_challenged(
    valid_pack: Path, verifier: JwtTokenVerifier, config: HostedAuthConfig
) -> None:
    with TestClient(protected_app(valid_pack, verifier, config)) as client:
        resp = client.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp.status_code == 401
        challenge = resp.headers.get("www-authenticate", "")
        assert challenge.lower().startswith("bearer")
        assert "resource_metadata=" in challenge


def test_invalid_token_is_rejected_over_http(
    valid_pack: Path,
    verifier: JwtTokenVerifier,
    config: HostedAuthConfig,
    other_key: rsa.RSAPrivateKey,
) -> None:
    with TestClient(protected_app(valid_pack, verifier, config)) as client:
        for bad in ("Bearer not-a-jwt", f"Bearer {mint(other_key)}"):
            resp = client.post(
                "/v1/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                headers={"authorization": bad},
            )
            assert resp.status_code == 401, bad


def test_protected_resource_metadata_is_served_at_the_advertised_path(
    valid_pack: Path, verifier: JwtTokenVerifier, config: HostedAuthConfig
) -> None:
    # RFC 9728 §3.1 — and the exact path the WWW-Authenticate challenge points at.
    with TestClient(protected_app(valid_pack, verifier, config)) as client:
        challenge = client.post("/v1/mcp", json={}).headers["www-authenticate"]
        advertised = challenge.split('resource_metadata="', 1)[1].split('"', 1)[0]
        path = advertised.split("https://runtime.example.com", 1)[1]
        assert path == "/.well-known/oauth-protected-resource/v1/mcp"
        document = client.get(path)
        assert document.status_code == 200
        body = document.json()
        assert body["resource"] == RESOURCE_URL
        assert ISSUER in [str(a).rstrip("/") for a in body["authorization_servers"]]


def test_health_endpoints_stay_open_and_leak_no_identity(
    valid_pack: Path, verifier: JwtTokenVerifier, config: HostedAuthConfig
) -> None:
    with TestClient(protected_app(valid_pack, verifier, config)) as client:
        for path in ("/healthz", "/readyz"):
            resp = client.get(path)
            assert resp.status_code == 200
            body = resp.text.lower()
            for leaked in ("principal", "token", "bearer", "sub", "client_id", "authorization"):
                assert leaked not in body, f"{path} leaked {leaked}"


# --- authenticated wire behaviour and principal binding ----------------------


async def _session(app: Any, token: str | None) -> Any:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    headers = {"authorization": f"Bearer {token}"} if token else {}
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost", headers=headers)
    return ClientSession, streamable_http_client, client


def _call(app: Any, token: str, calls: list[tuple[str, dict[str, Any]]]) -> list[Any]:
    async def scenario() -> list[Any]:
        ClientSession, streamable_http_client, hc = await _session(app, token)
        async with app.router.lifespan_context(app), hc:
            async with streamable_http_client("http://localhost/v1/mcp", http_client=hc) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    out = []
                    for name, args in calls:
                        out.append(await session.call_tool(name, args))
                    return out

    return asyncio.run(asyncio.wait_for(scenario(), timeout=60))


def _data(result: Any) -> dict[str, Any]:
    if getattr(result, "structured_content", None):
        return dict(result.structured_content)
    return dict(json.loads(result.content[0].text))


def test_valid_token_reaches_the_tools_and_capabilities_advertise_protection(
    valid_pack: Path,
    verifier: JwtTokenVerifier,
    config: HostedAuthConfig,
    signing_key: rsa.RSAPrivateKey,
) -> None:
    app = protected_app(valid_pack, verifier, config)
    (caps,) = _call(app, mint(signing_key), [("runtime_capabilities", {})])
    assert caps.is_error is False
    body = _data(caps)
    assert body["authentication"] == "oauth2_bearer"
    # Authentication buys identity, never new verbs.
    assert body["mode"] == "read_only"
    assert body["writes"] is False
    assert body["execution"] is False


def test_authentication_does_not_change_what_the_compiler_produces(
    valid_pack: Path,
    verifier: JwtTokenVerifier,
    config: HostedAuthConfig,
    signing_key: rsa.RSAPrivateKey,
) -> None:
    app = protected_app(valid_pack, verifier, config)
    (hosted,) = _call(app, mint(signing_key), [("compile_runtime", {"mission": MISSION})])
    hosted_digests = _data(hosted)["digests"]

    unauthenticated = build_server(valid_pack)
    plain = asyncio.run(unauthenticated.call_tool("compile_runtime", {"mission": MISSION}))
    plain_digests = _data(plain)["digests"]

    assert hosted_digests == plain_digests


async def _open(app: Any, token: str) -> Any:
    """Open one authenticated MCP session against an app whose lifespan is running."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    transport = httpx.ASGITransport(app=app)
    return (
        ClientSession,
        streamable_http_client,
        httpx.AsyncClient(
            transport=transport,
            base_url="http://localhost",
            headers={"authorization": f"Bearer {token}"},
        ),
    )


async def _session_do(app: Any, token: str, action: Any) -> Any:
    ClientSession, streamable_http_client, hc = await _open(app, token)
    async with hc:
        async with streamable_http_client("http://localhost/v1/mcp", http_client=hc) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await action(session)


def test_runs_are_owned_by_the_validated_principal_and_isolated_between_them(
    valid_pack: Path,
    verifier: JwtTokenVerifier,
    config: HostedAuthConfig,
    signing_key: rsa.RSAPrivateKey,
) -> None:
    app = protected_app(valid_pack, verifier, config)

    async def scenario() -> tuple[Any, BaseException, BaseException]:
        # The SDK's StreamableHTTPSessionManager is single-use per app, so every
        # session in this scenario shares one lifespan.
        async with app.router.lifespan_context(app):
            compiled = await _session_do(
                app,
                mint(signing_key, subject="user-a"),
                lambda s: s.call_tool("compile_runtime", {"mission": MISSION}),
            )
            run_id = _data(compiled)["run_id"]

            # The creating principal reads its own run.
            own = await _session_do(
                app,
                mint(signing_key, subject="user-a"),
                lambda s: s.read_resource(f"l9://runs/{run_id}"),
            )

            # A different subject on the same OAuth client is a different principal.
            try:
                await _session_do(
                    app,
                    mint(signing_key, subject="user-b"),
                    lambda s: s.read_resource(f"l9://runs/{run_id}"),
                )
                raise AssertionError("cross-principal read succeeded")
            except Exception as exc:  # noqa: BLE001
                cross = exc

            try:
                await _session_do(
                    app,
                    mint(signing_key, subject="user-b"),
                    lambda s: s.read_resource("l9://runs/run-that-never-existed"),
                )
                raise AssertionError("unknown-run read succeeded")
            except Exception as exc:  # noqa: BLE001
                unknown = exc

            return own, cross, unknown

    own, cross, unknown = asyncio.run(asyncio.wait_for(scenario(), timeout=90))

    assert json.loads(own.contents[0].text)["digests"]
    # Anti-enumerating: "not yours" and "never existed" must be indistinguishable.
    assert _shape(cross) == _shape(unknown), (
        f"cross-principal error {cross!r} is distinguishable from unknown-run error {unknown!r}"
    )


def _shape(error: BaseException) -> str:
    """The error as a reader sees it, with the run identifier masked out."""
    text = str(error)
    return f"{type(error).__name__}:{text.split('l9://runs/')[0]}"


def test_stdio_remains_unauthenticated_and_locally_owned(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    compiled = asyncio.run(server.call_tool("compile_runtime", {"mission": MISSION}))
    assert isinstance(compiled, CallToolResult)
    assert compiled.is_error is False
    run_id = _data(compiled)["run_id"]
    # Readable with no token at all: stdio is local and unauthenticated.
    read = asyncio.run(server.read_resource(f"l9://runs/{run_id}"))
    assert not isinstance(read, InputRequiredResult)
    assert json.loads(list(read)[0].content)["digests"]
    caps = asyncio.run(server.call_tool("runtime_capabilities", {}))
    assert _data(caps)["authentication"] == "none"
    assert LOCAL_PRINCIPAL == "local-stdio"


# --- architectural boundary --------------------------------------------------

COMPILER_STAGE_OWNERS = (
    "compiler",
    "models",
    "service",
    "pack",
    "graph",
    "parsing",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_auth_module_does_not_import_any_compiler_stage_owner() -> None:
    imports = _imported_modules(Path("src/l9_cognitive_runtime/mcp/auth.py"))
    for module in imports:
        assert not module.startswith("l9_cognitive_runtime."), (
            f"auth imports runtime module {module!r}; authentication must terminate "
            "at ingress and know nothing about compilation"
        )


def test_no_compiler_stage_owner_imports_auth() -> None:
    root = Path("src/l9_cognitive_runtime")
    offenders: list[str] = []
    for package in COMPILER_STAGE_OWNERS:
        target = root / package
        candidates = [target] if target.is_file() else list(target.rglob("*.py"))
        if target.with_suffix(".py").is_file():
            candidates.append(target.with_suffix(".py"))
        for path in candidates:
            if not path.is_file():
                continue
            if any("mcp.auth" in imported for imported in _imported_modules(path)):
                offenders.append(str(path))
    assert not offenders, f"compiler stage imports hosted auth: {offenders}"


def test_compile_pipeline_is_auth_agnostic() -> None:
    pipeline = Path("src/l9_cognitive_runtime/compiler/pipeline.py")
    source = pipeline.read_text(encoding="utf-8").lower()
    for token in ("oauth", "bearer", "jwt", "principal", "authorization", "token_verifier"):
        assert token not in source, f"CompilePipeline mentions {token!r}"
