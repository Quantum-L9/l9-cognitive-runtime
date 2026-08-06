"""Read-only MCP stdio server for the cognitive runtime (L9CR-MCP-008)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from l9_cognitive_runtime import __version__
from l9_cognitive_runtime.mcp.run_store import InMemoryRunStore
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

SERVER_NAME = "l9-cognitive-runtime"
READ_ONLY_TOOLS = (
    "runtime_capabilities",
    "compile_runtime",
    "get_bundle_digests",
    "list_pack_manifest",
    "validate_pack_path",
    "get_run",
)


def build_server(pack_root: Path | None = None) -> MCPServer:
    """Create a read-only MCP server bound to an optional pack root."""
    root = (pack_root or Path.cwd()).resolve()
    service = CognitiveRuntimeService()
    runs = InMemoryRunStore()
    mcp = MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=(
            "Read-only L9 Cognitive Runtime MCP. Compiles runtime bundles in memory; "
            "does not execute graphs or mutate the repository."
        ),
    )

    @mcp.tool()
    def runtime_capabilities() -> dict[str, Any]:
        """List read-only capabilities of this MCP server."""
        return {
            "server": SERVER_NAME,
            "version": __version__,
            "transport": "stdio",
            "mode": "read_only",
            "tools": list(READ_ONLY_TOOLS),
            "writes": False,
            "execution": False,
            "pack_root": str(root),
        }

    @mcp.tool()
    def compile_runtime(
        mission: str, task_type: str = "kernel_runtime_convergence"
    ) -> dict[str, Any]:
        """Compile a runtime bundle in memory for the given mission."""
        bundle = service.compile_runtime(
            CompileRequest(mission=mission, task_type=task_type, pack_root=root)
        )
        return {
            "digests": bundle.digests(),
            "intent": bundle.intent.to_canonical_dict(),
            "execution_contract_id": bundle.execution.contract_id,
            "graph_id": bundle.graph.graph_id,
            "terminal_node": bundle.graph.terminal_node,
            "provenance": None if bundle.provenance is None else bundle.provenance.to_dict(),
        }

    @mcp.tool()
    def get_bundle_digests(mission: str) -> dict[str, str]:
        """Return canonical digests for a freshly compiled in-memory bundle."""
        bundle = service.compile_runtime(CompileRequest(mission=mission, pack_root=root))
        return bundle.digests()

    @mcp.tool()
    def list_pack_manifest() -> dict[str, Any]:
        """Return verified pack provenance and listed file digests."""
        pack = PackLoader().load(root)
        return {
            "pack_ref": pack.provenance.pack_ref,
            "manifest_digest": pack.provenance.manifest_digest,
            "files": dict(pack.provenance.file_digests),
        }

    @mcp.tool()
    def validate_pack_path(relative_path: str) -> dict[str, Any]:
        """Resolve a relative pack path with traversal protection (read-only check)."""
        pack = PackLoader().load(root)
        resolved = pack.resolve(relative_path)
        return {"path": relative_path, "resolved": str(resolved), "exists": resolved.exists()}

    @mcp.resource("runtime://capabilities")
    def capabilities_resource() -> str:
        return json.dumps(runtime_capabilities(), indent=2, sort_keys=True)

    @mcp.resource("pack://manifest")
    def pack_manifest_resource() -> str:
        return json.dumps(list_pack_manifest(), indent=2, sort_keys=True)

    return mcp


def main() -> None:
    """Stdio-only entrypoint. Non-stdio transports are refused by omission."""
    import asyncio
    import os
    import sys

    if os.environ.get("L9_MCP_TRANSPORT", "stdio") != "stdio":
        print("error: only stdio transport is supported in L9CR-MCP-008", file=sys.stderr)
        raise SystemExit(2)
    pack_root = Path(os.environ["L9_PACK_ROOT"]) if os.environ.get("L9_PACK_ROOT") else Path.cwd()
    server = build_server(pack_root)
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
