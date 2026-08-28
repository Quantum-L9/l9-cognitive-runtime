"""LIVE-009/LIVE-010: static artifacts have no fresh authority; sealed packs
compile identically across CLI and MCP."""

from __future__ import annotations

import asyncio
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from l9_cognitive_runtime.deployment import build_deployment_pack
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40


def test_live009_static_contract_route_is_ignored(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    """A stale static FINAL_EXECUTION_CONTRACT.yaml does not influence a
    fresh mission that requires a different route."""
    stale_execution = {
        "contract_id": "FINAL_EXECUTION_CONTRACT",
        "contract_type": "universal_execution_contract",
        "source_activation_plan": "plan.yaml",
        "terminal_doctrine": "kernels/flawless_victory.yaml",
        "objective": "stale museum route",
        "authority_order": ["user task"],
        "kernel_activation": ["runtime/kernels/task/l9_engine_build_kernel.yaml"],
        "execution_sequence": ["run recursive improvement"],
        "validation_requirements": ["format"],
        "output_contract": ["summary"],
        "adapter_targets": ["cursor"],
    }
    pack = pack_builder(tmp_path / "pack", execution=stale_execution)
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(
            mission="Add safe retry behavior to this asynchronous payment worker.",
            pack_root=pack,
        )
    )
    # The live route selects developer_core — the stale static route (l9
    # engine build) has no effect.
    assert any(
        ref.endswith("developer_core_kernel.yaml") for ref in bundle.execution.kernel_activation
    )


def test_live010_cli_and_mcp_compile_same_semantics_from_sealed_pack(tmp_path: Path) -> None:
    pack_root = build_deployment_pack(ROOT, tmp_path / "pack", source_revision=REVISION)
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=pack_root)
    )

    from l9_cognitive_runtime.cli import main as cli_main
    from l9_cognitive_runtime.mcp import build_server

    server = build_server(pack_root)

    async def _mcp_compile() -> dict[str, Any]:
        result = await server.call_tool(
            "compile_runtime",
            {"mission": "Audit this repository.", "task_type": "kernel_runtime_convergence"},
        )
        structured = getattr(result, "structured_content", None)
        if structured:
            return dict(structured)
        parts = list(getattr(result, "content", []))
        text = "".join(str(getattr(part, "text", "")) for part in parts)
        return dict(json.loads(text))

    mcp = asyncio.run(_mcp_compile())
    assert mcp["digests"] == bundle.digests()

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert cli_main(["--mission", "Audit this repository.", "--pack-root", str(pack_root)]) == 0
    cli_payload = json.loads(buffer.getvalue())
    assert cli_payload["digests"] == bundle.digests()
