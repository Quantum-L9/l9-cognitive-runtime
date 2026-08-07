"""Streamable HTTP transport tests (L9CR-MCP-010).

No authentication is exercised or asserted here — that is MCP-011.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx2 as httpx  # the mcp SDK vendors httpx as httpx2
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS
from l9_cognitive_runtime.mcp.http import (
    ConcurrencyLimitMiddleware,
    RequestTimeoutMiddleware,
    create_http_app,
)

# --- health / readiness / parity (no credentials) ---------------------------


def test_health_and_ready(valid_pack: Path) -> None:
    with TestClient(create_http_app(valid_pack)) as client:
        health = client.get("/healthz").json()
        assert health["status"] == "ok"
        assert "principal" not in health and "token" not in health
        ready = client.get("/readyz").json()
        assert ready["status"] == "ready"
        assert ready["tools"] == sorted(READ_ONLY_TOOLS)


def test_tool_surface_matches_stdio(valid_pack: Path) -> None:
    with TestClient(create_http_app(valid_pack)) as client:
        ready = client.get("/readyz").json()
        assert set(ready["tools"]) == set(READ_ONLY_TOOLS)


# --- controls ----------------------------------------------------------------


def test_oversized_request_rejected(valid_pack: Path) -> None:
    with TestClient(create_http_app(valid_pack)) as client:
        big = b"x" * (1_048_576 + 1)
        resp = client.post("/v1/mcp", content=big, headers={"content-type": "application/json"})
        assert resp.status_code == 413


def test_disallowed_origin_rejected(valid_pack: Path) -> None:
    with TestClient(create_http_app(valid_pack)) as client:
        resp = client.get("/healthz", headers={"origin": "http://evil.example"})
        assert resp.status_code == 403


def test_allowed_origin_passes(valid_pack: Path) -> None:
    app = create_http_app(valid_pack, allowed_origins=frozenset({"http://ok.example"}))
    with TestClient(app) as client:
        resp = client.get("/healthz", headers={"origin": "http://ok.example"})
        assert resp.status_code == 200


def test_no_legacy_sse_route(valid_pack: Path) -> None:
    with TestClient(create_http_app(valid_pack)) as client:
        assert client.get("/sse").status_code == 404
        assert client.get("/v1/sse").status_code == 404


def test_mcp_endpoint_is_mounted(valid_pack: Path) -> None:
    # A malformed/unsessioned request is handled by the MCP app (not a 404).
    with TestClient(create_http_app(valid_pack)) as client:
        resp = client.post("/v1/mcp", json={"bad": "request"})
        assert resp.status_code != 404


# --- concurrency / timeout middleware (deterministic, isolated) --------------


def _slow_app(*middleware: Middleware, delay: float = 0.4) -> Starlette:
    async def slow(_: object) -> PlainTextResponse:
        await asyncio.sleep(delay)
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/slow", slow)], middleware=list(middleware))


def test_concurrency_limit_sheds_load() -> None:
    app = _slow_app(
        Middleware(ConcurrencyLimitMiddleware, limit=1, acquire_timeout=0.05), delay=0.3
    )

    async def scenario() -> list[int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            results = await asyncio.gather(
                client.get("/slow"), client.get("/slow"), return_exceptions=False
            )
            return [r.status_code for r in results]

    codes = asyncio.run(scenario())
    assert 503 in codes  # one request shed under the limit of 1


def test_request_timeout_returns_504() -> None:
    app = _slow_app(Middleware(RequestTimeoutMiddleware, timeout_seconds=0.1), delay=0.5)

    async def scenario() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.get("/slow")
            return resp.status_code

    assert asyncio.run(scenario()) == 504


# --- wire-level: HTTP MCP initialize + tool parity ---------------------------


def test_http_initialize_and_tool_parity(valid_pack: Path) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def scenario() -> None:
        app = create_http_app(valid_pack)
        # Run the app lifespan (starts the MCP session manager) without a server.
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as hc:
                async with streamable_http_client("http://localhost/v1/mcp", http_client=hc) as (
                    read,
                    write,
                ):
                    async with ClientSession(read, write) as session:
                        init = await session.initialize()
                        assert init.server_info.name == "l9-cognitive-runtime"
                        tools = await session.list_tools()
                        assert {t.name for t in tools.tools} == set(READ_ONLY_TOOLS)
                        called = await session.call_tool("compile_runtime", {"mission": "http e2e"})
                        assert called.is_error is False

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))
