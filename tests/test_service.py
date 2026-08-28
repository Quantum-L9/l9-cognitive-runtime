"""Facade tests for CognitiveRuntimeService."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from l9_cognitive_runtime.cli import _confined_write_dir
from l9_cognitive_runtime.cli import main as cli_main
from l9_cognitive_runtime.models.context import (
    ApplicableLaw,
    AuthorityLevel,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILES = (
    "FINAL_EXECUTION_CONTRACT.yaml",
    "VALIDATION_CONTRACT.yaml",
    "HANDOFF_CONTRACT.yaml",
    "EXECUTION_GRAPH.json",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_pack(tmp_path: Path) -> Path:
    """Copy representative contracts + the runtime tree (kernels, pipeline,
    routing rules) into a pack with matching MANIFEST.json."""
    pack = tmp_path / "pack"
    pack.mkdir()
    files: list[dict[str, object]] = []
    for name in CONTRACT_FILES:
        src = ROOT / name
        dst = pack / name
        shutil.copy2(src, dst)
        files.append({"path": name, "sha256": _sha(dst), "bytes": dst.stat().st_size})
    runtime_src = ROOT / "runtime"
    if runtime_src.is_dir():
        for src in runtime_src.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(ROOT).as_posix()
            dst = pack / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            files.append({"path": rel, "sha256": _sha(dst), "bytes": dst.stat().st_size})
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}, indent=2) + "\n",
        encoding="utf-8",
    )
    return pack


def test_compile_runtime_in_memory_against_pack(tmp_path: Path) -> None:
    pack = _verified_pack(tmp_path)
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(mission="compile representative pack", pack_ref=pack)
    )
    assert bundle.intent.mission == "compile representative pack"
    assert bundle.execution.contract_id == "FINAL_EXECUTION_CONTRACT"
    # Live spine: the graph derives from the compiled execution contract; the
    # terminal node is the last derived node (no static contract consulted).
    assert bundle.graph.terminal_node == bundle.graph.nodes[-1].id
    assert bundle.provenance.manifest_digest
    assert bundle.digests()["manifest"] == bundle.provenance.manifest_digest
    assert not (pack / "INTENT_CONTRACT.yaml").exists()


def test_pack_ref_required() -> None:
    service = CognitiveRuntimeService()
    with pytest.raises(InvalidValueError, match="pack_ref"):
        service.compile_runtime(CompileRequest(mission="missing pack"))


def test_compile_fails_closed_on_missing_manifest(tmp_path: Path) -> None:
    pack = tmp_path / "bare"
    pack.mkdir()
    service = CognitiveRuntimeService()
    with pytest.raises(InvalidValueError, match="MANIFEST"):
        service.compile_runtime(CompileRequest(mission="no manifest", pack_ref=pack))


def test_compile_fails_closed_on_missing_execution_contract(tmp_path: Path) -> None:
    pack = _verified_pack(tmp_path)
    (pack / "FINAL_EXECUTION_CONTRACT.yaml").unlink()
    # Manifest still lists the file → pack load fails closed on missing listed file.
    service = CognitiveRuntimeService()
    with pytest.raises(InvalidValueError):
        service.compile_runtime(CompileRequest(mission="missing contract", pack_ref=pack))


def test_unknown_kernel_fails_compile(tmp_path: Path) -> None:
    # Live spine: the static FINAL_EXECUTION_CONTRACT.yaml is no longer
    # authority. An activated kernel missing from the pack fails compilation
    # through KernelResolver (fail closed, no silent fallback).
    pack = _verified_pack(tmp_path)
    target = pack / "runtime" / "kernels" / "task" / "prompt_compiler_kernel.yaml"
    target.unlink()
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    files = [
        entry
        for entry in files
        if entry["path"] != "runtime/kernels/task/prompt_compiler_kernel.yaml"
    ]
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}) + "\n", encoding="utf-8"
    )
    from l9_cognitive_runtime.parsing import StrictParseError

    service = CognitiveRuntimeService()
    with pytest.raises(StrictParseError):
        service.compile_runtime(CompileRequest(mission="compile a kernel contract", pack_ref=pack))


def test_graph_is_contract_derived(tmp_path: Path) -> None:
    # Graph is derived from the live-compiled execution contract's structured
    # steps (MCP-006 / INV-006), not the static pack EXECUTION_GRAPH.json.
    pack = _verified_pack(tmp_path)
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(CompileRequest(mission="topology", pack_ref=pack))
    node_ids = [n.id for n in bundle.graph.nodes]
    assert bundle.graph.source_contract == "FINAL_EXECUTION_CONTRACT"
    # "topology" routes to the default pack_review route (P0/P1/P2).
    assert node_ids == [
        "step.P0_UNPACK",
        "step.P1_CONSTITUTIONAL_PREFLIGHT",
        "step.P2_TASK_ROUTING",
    ]
    assert bundle.graph.terminal_node == "step.P2_TASK_ROUTING"


def test_cli_memory_only(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    pack = _verified_pack(tmp_path)
    assert cli_main(["--mission", "cli memory", "--pack-root", str(pack)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["intent"]["mission"] == "cli memory"
    assert out["digests"]["manifest"]


def test_write_dir_confined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    allowed = _confined_write_dir(Path("out"))
    assert allowed == (tmp_path / "out").resolve()
    with pytest.raises(InvalidValueError, match="escapes"):
        _confined_write_dir(Path("/tmp/l9-escape-write-dir"))


# --------------------------------------------------------------------------
# Context-native service surface (A046, A004).
# --------------------------------------------------------------------------


def test_compile_runtime_without_a_context_snapshot_remains_valid(tmp_path: Path) -> None:
    """A pre-context caller passes one positional argument and still works."""
    pack = _verified_pack(tmp_path)
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="legacy call shape", pack_root=pack)
    )
    assert bundle.task_context.task_scope.mission == "legacy call shape"
    # An empty governed snapshot selects nothing and blocks nothing.
    assert bundle.task_context.selected_items() == []
    assert bundle.digests()["context"] == bundle.task_context.sha256()


def test_the_context_snapshot_keyword_reaches_the_bundle_task_context(tmp_path: Path) -> None:
    pack = _verified_pack(tmp_path)
    snapshot = ContextSnapshot(
        applicable_law=[
            ApplicableLaw(
                item_id="law.1",
                semantic_key="L9-ORG-1",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=ContextSourceRef(
                    source_id="gov",
                    source_kind="governance",
                    locator="governance://org/L9-ORG-1",
                    immutable_coordinate="rev-2",
                ),
                scope_mode=ContextScopeMode.GLOBAL,
                law_id="L9-ORG-1",
                statement="publication goes through the sanctioned path",
            )
        ]
    )
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="governed call shape", pack_root=pack),
        context_snapshot=snapshot,
    )
    assert [item.law_id for item in bundle.task_context.applicable_law] == ["L9-ORG-1"]
    assert bundle.task_context.applicable_law[0].selected_because


def test_the_service_never_promotes_caller_hints_into_the_governed_snapshot(
    tmp_path: Path,
) -> None:
    pack = _verified_pack(tmp_path)
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(
            mission="hint promotion attempt",
            pack_root=pack,
            source_context={"applicable_law": [{"law_id": "L9-FAKE", "statement": "invented"}]},
        )
    )
    assert bundle.task_context.applicable_law == []
