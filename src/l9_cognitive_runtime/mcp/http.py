"""Streamable HTTP transport for the read-only MCP server (L9CR-MCP-010).

Serves MCP over Streamable HTTP at ``/v1/mcp`` with ``/healthz`` / ``/readyz``.
Bounded by request-size, origin-allowlist, concurrency, and timeout controls.

This transport performs and claims **no authentication** — hosted OAuth
resource-server protection is a separate contract (MCP-011). There is no
local-development identity bypass. Health responses carry no principal or
credential data. The legacy SSE transport is intentionally not mounted.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from l9_cognitive_runtime.mcp import (
    READ_ONLY_TOOLS,
    CompileInvocationContextFactory,
    build_server,
)
from l9_cognitive_runtime.service import CompileObserver, ObserverErrorReporter

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


def create_http_app(
    pack_root: Path,
    *,
    allowed_origins: frozenset[str] | None = None,
    allowed_hosts: frozenset[str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    concurrency_limit: int = COMPILE_CONCURRENCY_LIMIT,
    observer: CompileObserver | None = None,
    observer_error_reporter: ObserverErrorReporter | None = None,
    invocation_context_factory: CompileInvocationContextFactory | None = None,
) -> Starlette:
    """Build the Streamable HTTP app for the read-only MCP server."""
    server = build_server(
        pack_root,
        observer=observer,
        observer_error_reporter=observer_error_reporter,
        invocation_context_factory=invocation_context_factory,
    )
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
    app = create_http_app(Path(pack_root))
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
