"""Streamable HTTP transport wrapper for the read-only MCP server (L9CR-MCP-010)."""

from __future__ import annotations

import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from l9_cognitive_runtime.mcp import build_server


def create_http_app(pack_root: Path | None = None) -> Starlette:
    """Host MCP over Streamable HTTP at /v1/mcp with health/readiness."""
    server = build_server(pack_root)
    mcp_asgi = server.streamable_http_app()

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "streamable_http"})

    async def ready(_: Request) -> JSONResponse:
        tools = sorted(server._tool_manager._tools.keys())  # noqa: SLF001
        return JSONResponse({"status": "ready", "tools": tools})

    return Starlette(
        routes=[
            Route("/healthz", health, methods=["GET"]),
            Route("/readyz", ready, methods=["GET"]),
            Mount("/v1/mcp", app=mcp_asgi),
        ]
    )


def main() -> None:
    import uvicorn

    if os.environ.get("L9_MCP_TRANSPORT") == "stdio":
        raise SystemExit("use l9-cognitive-runtime-mcp for stdio")
    pack = Path(os.environ["L9_PACK_ROOT"]) if os.environ.get("L9_PACK_ROOT") else Path.cwd()
    app = create_http_app(pack)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
