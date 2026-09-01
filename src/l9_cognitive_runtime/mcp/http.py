"""Streamable HTTP transport for the read-only MCP server (L9CR-MCP-010).

Serves MCP over Streamable HTTP at ``/v1/mcp`` with ``/healthz`` / ``/readyz``.
Bounded by request-size, origin-allowlist, concurrency, and timeout controls.

Hosted OAuth 2.0 / OIDC resource-server protection (MCP-011) is applied here, at
the ingress boundary, when deployment configuration supplies an issuer, audience
and resource URL (see ``l9_cognitive_runtime.mcp.auth``). Authentication
terminates here and establishes principal identity; the compiler below is
unaware of it and produces identical output with or without a token. There is no
local-development identity bypass. Health responses carry no principal or
credential data. The legacy SSE transport is intentionally not mounted.

When no OAuth configuration is present the transport serves unprotected, which is
what the local and CI smokes rely on. A hosted deployment asserts protection with
``L9_REQUIRE_AUTH=true``, which refuses to start unprotected rather than trusting
an operator to remember the other three variables.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server
from l9_cognitive_runtime.mcp.auth import (
    HostedAuthConfig,
    HostedAuthConfigurationError,
    JwtTokenVerifier,
)

MCP_PATH = "/v1/mcp"
MAX_BODY_BYTES = 1_048_576  # 1 MiB
DEFAULT_TIMEOUT_SECONDS = 60.0
COMPILE_CONCURRENCY_LIMIT = 8
DEFAULT_BIND = "127.0.0.1"

_Dispatch = Callable[[Request], Awaitable[Response]]


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared body exceeds ``max_bytes`` with 413."""

    def __init__(self, app: Any, max_bytes: int = MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: _Dispatch) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > self.max_bytes:
            return JSONResponse({"error": "request entity too large"}, status_code=413)
        return await call_next(request)


class OriginAllowlistMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin requests unless the Origin is explicitly allowlisted.

    CORS is disabled by default (empty allowlist), so any request carrying an
    Origin header that is not on the list is refused with 403.
    """

    def __init__(self, app: Any, allowed_origins: frozenset[str]) -> None:
        super().__init__(app)
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next: _Dispatch) -> Response:
        origin = request.headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            return JSONResponse({"error": "origin not allowed"}, status_code=403)
        return await call_next(request)


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """Bound concurrent in-flight requests; shed load with 503 when saturated."""

    def __init__(
        self,
        app: Any,
        limit: int = COMPILE_CONCURRENCY_LIMIT,
        acquire_timeout: float = 5.0,
    ) -> None:
        super().__init__(app)
        self._sem = asyncio.Semaphore(limit)
        self._acquire_timeout = acquire_timeout

    async def dispatch(self, request: Request, call_next: _Dispatch) -> Response:
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self._acquire_timeout)
        except TimeoutError:
            return JSONResponse({"error": "server busy"}, status_code=503)
        try:
            return await call_next(request)
        finally:
            self._sem.release()


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Fail a request that exceeds ``timeout_seconds`` with 504."""

    def __init__(self, app: Any, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: _Dispatch) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except TimeoutError:
            return JSONResponse({"error": "request timed out"}, status_code=504)


def _allowed_origins() -> frozenset[str]:
    raw = os.environ.get("L9_ALLOWED_ORIGINS", "").strip()
    return frozenset(o.strip() for o in raw.split(",") if o.strip())


def _allowed_hosts() -> frozenset[str]:
    raw = os.environ.get("L9_ALLOWED_HOSTS", "").strip()
    hosts = {h.strip() for h in raw.split(",") if h.strip()}
    return frozenset(hosts or {"127.0.0.1", "localhost"})


def resolve_hosted_auth(
    env: dict[str, str] | None = None,
) -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Resolve the hosted resource-server wiring from deployment configuration.

    Returns ``(None, None)`` when no OAuth configuration is present. Raises when
    ``L9_REQUIRE_AUTH`` asserts protection that the configuration cannot deliver:
    a deployment that means to be protected must fail to start rather than come
    up open.
    """
    source = dict(os.environ) if env is None else env
    config = HostedAuthConfig.from_env(source)
    required = source.get("L9_REQUIRE_AUTH", "").strip().lower() in {"1", "true", "yes"}
    if config is None:
        if required:
            raise HostedAuthConfigurationError(
                "L9_REQUIRE_AUTH is set but no OAuth configuration is present; "
                "set L9_OAUTH_ISSUER, L9_OAUTH_AUDIENCE and L9_MCP_RESOURCE_URL"
            )
        return None, None
    return JwtTokenVerifier(config), config.to_auth_settings()


def create_http_app(
    pack_root: Path,
    *,
    allowed_origins: frozenset[str] | None = None,
    allowed_hosts: frozenset[str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    concurrency_limit: int = COMPILE_CONCURRENCY_LIMIT,
    token_verifier: TokenVerifier | None = None,
    auth_settings: AuthSettings | None = None,
) -> Starlette:
    """Build the Streamable HTTP app for the read-only MCP server."""
    server = build_server(pack_root, token_verifier=token_verifier, auth_settings=auth_settings)
    origins = _allowed_origins() if allowed_origins is None else allowed_origins
    hosts = _allowed_hosts() if allowed_hosts is None else allowed_hosts
    # DNS-rebinding protection at the transport layer (defense in depth alongside
    # the origin-allowlist and body-size middleware below).
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(origins),
    )
    mcp_asgi = server.streamable_http_app(  # serves "/mcp" internally
        transport_security=security,
        max_request_body_size=MAX_BODY_BYTES,
    )

    # RFC 9728 §3.1 puts protected-resource metadata at
    # /.well-known/oauth-protected-resource<resource-path>, an absolute path on the
    # host. The SDK registers it on the inner app, which we mount under /v1 — so
    # left alone it would only answer at /v1/.well-known/..., where no client looks
    # and where the WWW-Authenticate pointer the SDK itself emits does not point.
    # Lifting the SDK's own route (handler included, so the document is not
    # re-implemented) onto the parent restores the advertised location.
    well_known_routes = [
        route
        for route in mcp_asgi.routes
        if isinstance(route, Route) and route.path.startswith("/.well-known/")
    ]

    async def healthz(_: Request) -> JSONResponse:
        # No principal or credential data.
        return JSONResponse({"status": "ok", "transport": "streamable_http"})

    async def readyz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ready", "tools": sorted(READ_ONLY_TOOLS)})

    @asynccontextmanager
    async def lifespan(_: Starlette) -> Any:
        # Propagate the MCP session-manager lifespan through the parent app.
        async with mcp_asgi.router.lifespan_context(mcp_asgi):
            yield

    middleware = [
        Middleware(OriginAllowlistMiddleware, allowed_origins=origins),
        Middleware(MaxBodySizeMiddleware),
        Middleware(RequestTimeoutMiddleware, timeout_seconds=timeout_seconds),
        Middleware(ConcurrencyLimitMiddleware, limit=concurrency_limit),
    ]
    return Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Route("/readyz", readyz, methods=["GET"]),
            *well_known_routes,
            Mount("/v1", app=mcp_asgi),  # mcp_asgi "/mcp" -> "/v1/mcp"
        ],
        middleware=middleware,
        lifespan=lifespan,
    )


def main() -> None:
    """HTTP entrypoint (separate from the stdio console script)."""
    import uvicorn

    if os.environ.get("L9_MCP_TRANSPORT") == "stdio":
        print("error: use l9-cognitive-runtime-mcp for stdio transport", file=sys.stderr)
        raise SystemExit(2)
    pack_root = os.environ.get("L9_PACK_ROOT")
    if not pack_root:
        print("error: L9_PACK_ROOT is required", file=sys.stderr)
        raise SystemExit(2)
    token_verifier, auth_settings = resolve_hosted_auth()
    if token_verifier is None:
        print(
            "warning: serving MCP over HTTP without authentication; "
            "set L9_OAUTH_ISSUER/L9_OAUTH_AUDIENCE/L9_MCP_RESOURCE_URL to protect it, "
            "and L9_REQUIRE_AUTH=true to make an unprotected start a failure",
            file=sys.stderr,
        )
    app = create_http_app(
        Path(pack_root), token_verifier=token_verifier, auth_settings=auth_settings
    )
    uvicorn.run(
        app,
        host=os.environ.get("L9_BIND_HOST", DEFAULT_BIND),
        port=int(os.environ.get("PORT", "8080")),
        # Honor forwarded headers only behind trusted proxies.
        proxy_headers=os.environ.get("L9_TRUST_PROXY", "").lower() == "true",
        forwarded_allow_ips=os.environ.get("L9_FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
