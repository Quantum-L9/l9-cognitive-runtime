"""Read-only MCP stdio server for the cognitive runtime (L9CR-MCP-008B).

Exposes the deterministic compiler over MCP stdio. Invariants:

- stdio transport only; any other transport is refused.
- An explicit pack root is required (``L9_PACK_ROOT``); there is no
  working-directory fallback and no arbitrary filesystem path is accepted.
- Every compile runs against the verified, manifest-bound pack and carries
  provenance. No tool executes shell commands, mutates the repository, or
  executes graphs — the surface is read-only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from l9_cognitive_runtime import __version__
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader, RuntimePack
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

SERVER_NAME = "l9-cognitive-runtime"
DEFAULT_TASK_TYPE = "kernel_runtime_convergence"
READ_ONLY_TOOLS = (
    "runtime_capabilities",
    "compile_intent",
    "plan_kernel_activation",
    "compile_runtime",
    "validate_runtime_bundle",
)


def _capabilities(pack: RuntimePack) -> dict[str, Any]:
    return {
        "server": SERVER_NAME,
        "version": __version__,
        "transport": "stdio",
        "mode": "read_only",
        "tools": list(READ_ONLY_TOOLS),
        "writes": False,
        "execution": False,
        "shell": False,
        "pack_ref": pack.provenance.pack_ref,
        "manifest_digest": pack.provenance.manifest_digest,
    }


def build_server(pack_root: Path) -> MCPServer:
    """Create a read-only MCP server bound to an explicit, verified pack root."""
    root = pack_root.resolve()
    if not root.is_dir():
        raise InvalidValueError("pack_root must be an existing directory", path=str(root))
    # Fail closed at startup: the pack must load and verify.
    pack = PackLoader().load(root)
    pack_ref = str(pack.manifest.get("pack_name") or root.name)
    service = CognitiveRuntimeService()

    def _compile(mission: str, task_type: str = DEFAULT_TASK_TYPE) -> Any:
        return service.compile_runtime(
            CompileRequest(mission=mission, task_type=task_type, pack_root=root)
        )

    def _require_bound_pack(requested: str) -> None:
        if requested != pack_ref:
            raise InvalidValueError("unknown pack_ref", path=requested)

    def _read_pack_file(relative: str) -> str:
        # pack.resolve confines beneath the pack root and rejects traversal.
        return pack.resolve(relative).read_text(encoding="utf-8")

    mcp = MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=(
            "Read-only L9 Cognitive Runtime MCP. Compiles runtime bundles in memory "
            "against a verified pack; does not execute graphs, run shell commands, or "
            "mutate the repository."
        ),
    )

    @mcp.tool()
    def runtime_capabilities() -> dict[str, Any]:
        """List the read-only capabilities of this MCP server."""
        return _capabilities(pack)

    @mcp.tool()
    def compile_intent(mission: str, task_type: str = DEFAULT_TASK_TYPE) -> dict[str, Any]:
        """Compile the canonical intent contract for a mission (read-only)."""
        bundle = _compile(mission, task_type)
        return {
            "intent": bundle.intent.to_canonical_dict(),
            "intent_digest": bundle.digests()["intent"],
        }

    @mcp.tool()
    def plan_kernel_activation(mission: str) -> dict[str, Any]:
        """Return the contract's kernel activation plan (read-only)."""
        bundle = _compile(mission)
        return {
            "kernel_activation": list(bundle.execution.kernel_activation),
            "execution_sequence": list(bundle.execution.execution_sequence),
            "execution_digest": bundle.digests()["execution"],
        }

    @mcp.tool()
    def compile_runtime(mission: str, task_type: str = DEFAULT_TASK_TYPE) -> dict[str, Any]:
        """Compile a full runtime bundle in memory (read-only)."""
        bundle = _compile(mission, task_type)
        return {
            "digests": bundle.digests(),
            "execution_contract_id": bundle.execution.contract_id,
            "graph_id": bundle.graph.graph_id,
            "terminal_node": bundle.graph.terminal_node,
            "provenance": bundle.provenance.to_dict(),
        }

    @mcp.tool()
    def validate_runtime_bundle(mission: str) -> dict[str, Any]:
        """Compile and validate a runtime bundle's integrity (read-only)."""
        bundle = _compile(mission)
        digests = bundle.digests()
        checks = {
            "all_digests_present": all(digests.values()),
            "graph_has_terminal": bool(bundle.graph.terminal_node),
            "provenance_present": bundle.provenance is not None,
        }
        return {"valid": all(checks.values()), "digests": digests, "checks": checks}

    @mcp.resource("l9://runtime/version")
    def runtime_version_resource() -> str:
        return __version__

    @mcp.resource("l9://runtime/capabilities")
    def runtime_capabilities_resource() -> str:
        return json.dumps(_capabilities(pack), indent=2, sort_keys=True)

    @mcp.resource("l9://packs/{pack_ref}/manifest")
    def pack_manifest_resource(pack_ref: str) -> str:
        _require_bound_pack(pack_ref)
        return json.dumps(
            {
                "pack_ref": pack.provenance.pack_ref,
                "manifest_digest": pack.provenance.manifest_digest,
                "files": dict(pack.provenance.file_digests),
            },
            indent=2,
            sort_keys=True,
        )

    @mcp.resource("l9://packs/{pack_ref}/schemas/{schema_name}")
    def pack_schema_resource(pack_ref: str, schema_name: str) -> str:
        _require_bound_pack(pack_ref)
        return _read_pack_file(f"schemas/{schema_name}")

    @mcp.resource("l9://packs/{pack_ref}/kernels/{kernel_id}")
    def pack_kernel_resource(pack_ref: str, kernel_id: str) -> str:
        _require_bound_pack(pack_ref)
        return _read_pack_file(f"kernels/{kernel_id}")

    return mcp


def main() -> None:
    """Stdio-only entrypoint. Non-stdio transports and missing pack roots are refused."""
    transport = os.environ.get("L9_MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        print("error: only stdio transport is supported (L9CR-MCP-008B)", file=sys.stderr)
        raise SystemExit(2)
    pack_root = os.environ.get("L9_PACK_ROOT")
    if not pack_root:
        print(
            "error: L9_PACK_ROOT is required (no working-directory fallback)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    server = build_server(Path(pack_root))
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
