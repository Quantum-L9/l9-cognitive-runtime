"""Bounded Manus-facing MCP adapter for the L9 Cognitive Runtime.

This local stdio adapter is intentionally a narrow alias of the package-owned
read-only Cog MCP surface. It binds a single explicit, manifest-verified pack at
startup and exposes exactly six ``cog_``-namespaced compiler operations. It does
not execute graphs, invoke a shell, accept a caller-selected pack, access a
repository, or create a generic runtime execution interface.

The public, OAuth-protected HTTP deployment will expose the same underlying Cog
contract independently. This adapter exists only to make the verified compiler
available to the Manus MCP client while that release path is under review.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS
from l9_cognitive_runtime.mcp import build_server as _build_server
from l9_cognitive_runtime.models.errors import InvalidValueError

MANUS_SERVER_NAME = "l9-cognitive-runtime-manus"
MANUS_TOOL_PREFIX = "cog_"
MANUS_READ_ONLY_TOOLS = tuple(f"{MANUS_TOOL_PREFIX}{tool}" for tool in READ_ONLY_TOOLS)


def build_server(pack_root: Path) -> MCPServer:
    """Build the fixed, read-only Cog surface used by the Manus connector.

    The underlying server verifies the supplied pack before registering any
    tool. ``pack_root`` is a connector-owned environment value, not a tool
    parameter, so a caller cannot select arbitrary filesystem content.
    """
    return _build_server(
        pack_root,
        server_name=MANUS_SERVER_NAME,
        tool_name_prefix=MANUS_TOOL_PREFIX,
    )


def main() -> None:
    """Run the bounded adapter over local MCP stdio only."""
    transport = os.environ.get("L9_MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        print("error: only stdio transport is supported by the Manus Cog adapter", file=sys.stderr)
        raise SystemExit(2)
    pack_root = os.environ.get("L9_PACK_ROOT")
    if not pack_root:
        print("error: L9_PACK_ROOT is required (no working-directory fallback)", file=sys.stderr)
        raise SystemExit(2)
    try:
        server = build_server(Path(pack_root))
    except InvalidValueError as exc:
        print(f"error: verified Cog pack required: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
