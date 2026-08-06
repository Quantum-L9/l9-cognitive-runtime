"""Facade tests for CognitiveRuntimeService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_cognitive_runtime.cli import _confined_write_dir, main as cli_main
from l9_cognitive_runtime.models.errors import InvalidValueError
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
    # Memory-only compile must not require fixed repository output files.
    assert not (ROOT / "INTENT_CONTRACT.yaml").exists()


def test_pack_root_required() -> None:
    service = CognitiveRuntimeService()
    with pytest.raises(InvalidValueError, match="pack_root is required"):
        service.compile_runtime(CompileRequest(mission="missing pack"))


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


def test_write_dir_confined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    allowed = _confined_write_dir(Path("out"))
    assert allowed == (tmp_path / "out").resolve()
    with pytest.raises(InvalidValueError, match="escapes"):
        _confined_write_dir(Path("/tmp/l9-escape-write-dir"))
