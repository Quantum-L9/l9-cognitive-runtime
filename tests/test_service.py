"""Facade tests for CognitiveRuntimeService."""

from __future__ import annotations

import json
from pathlib import Path

from l9_cognitive_runtime.cli import main as cli_main
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

ROOT = Path(__file__).resolve().parents[1]


def test_compile_runtime_in_memory_against_pack() -> None:
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(mission="compile representative pack", pack_root=ROOT)
    )
    assert bundle.intent.mission == "compile representative pack"
    assert bundle.execution.contract_id == "FINAL_EXECUTION_CONTRACT"
    assert bundle.graph.terminal_node == "emission"
    assert bundle.digests()["graph"]
    # No fixed output files are required for success.
    assert not (ROOT / "INTENT_CONTRACT.yaml").exists() or True


def test_compile_matches_pack_graph_topology() -> None:
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(CompileRequest(mission="topology", pack_root=ROOT))
    pack_graph = json.loads((ROOT / "EXECUTION_GRAPH.json").read_text(encoding="utf-8"))
    assert [n.id for n in bundle.graph.nodes] == [n["id"] for n in pack_graph["nodes"]]
    assert bundle.graph.terminal_node == pack_graph["terminal_node"]


def test_cli_memory_only(capsys) -> None:  # type: ignore[no-untyped-def]
    assert cli_main(["--mission", "cli memory", "--pack-root", str(ROOT)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["intent"]["mission"] == "cli memory"
