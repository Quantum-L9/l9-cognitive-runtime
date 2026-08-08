"""Facade tests for CognitiveRuntimeService."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from l9_cognitive_runtime.cli import _confined_write_dir
from l9_cognitive_runtime.cli import main as cli_main
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
    """Copy representative contracts + kernels into a pack with matching MANIFEST.json."""
    pack = tmp_path / "pack"
    pack.mkdir()
    files: list[dict[str, object]] = []
    for name in CONTRACT_FILES:
        src = ROOT / name
        dst = pack / name
        shutil.copy2(src, dst)
        files.append({"path": name, "sha256": _sha(dst), "bytes": dst.stat().st_size})
    kernels_src = ROOT / "runtime" / "kernels"
    if kernels_src.is_dir():
        for src in kernels_src.rglob("*"):
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
    assert bundle.graph.terminal_node == "emission"
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
    pack = _verified_pack(tmp_path)
    contract = (pack / "FINAL_EXECUTION_CONTRACT.yaml").read_text(encoding="utf-8")
    contract = contract.replace(
        "runtime/kernels/task/repo_auditor_kernel.yaml",
        "runtime/kernels/task/does_not_exist_kernel.yaml",
    )
    (pack / "FINAL_EXECUTION_CONTRACT.yaml").write_text(contract, encoding="utf-8")
    # Refresh manifest hash for the mutated contract.
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    for entry in files:
        if entry["path"] == "FINAL_EXECUTION_CONTRACT.yaml":
            entry["sha256"] = _sha(pack / "FINAL_EXECUTION_CONTRACT.yaml")
            entry["bytes"] = (pack / "FINAL_EXECUTION_CONTRACT.yaml").stat().st_size
    manifest = {"pack_name": "test-pack", "files": files}
    (pack / "MANIFEST.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    from l9_cognitive_runtime.parsing import StrictParseError

    service = CognitiveRuntimeService()
    with pytest.raises(StrictParseError):
        service.compile_runtime(CompileRequest(mission="bad kernel", pack_ref=pack))


def test_compile_matches_pack_graph_topology(tmp_path: Path) -> None:
    pack = _verified_pack(tmp_path)
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(CompileRequest(mission="topology", pack_ref=pack))
    pack_graph = json.loads((pack / "EXECUTION_GRAPH.json").read_text(encoding="utf-8"))
    assert [n.id for n in bundle.graph.nodes] == [n["id"] for n in pack_graph["nodes"]]
    assert bundle.graph.terminal_node == pack_graph["terminal_node"]


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
