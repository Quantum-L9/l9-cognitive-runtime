"""Tamper, traversal, and provenance tests for PackLoader."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest, RuntimeBundle


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tiny_pack(tmp_path: Path) -> Path:
    (tmp_path / "ok.txt").write_text("ok\n", encoding="utf-8")
    manifest = {
        "pack_name": "tiny",
        "files": [{"path": "ok.txt", "sha256": _sha(tmp_path / "ok.txt"), "bytes": 3}],
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_load_pack_provenance(tmp_path: Path) -> None:
    root = _tiny_pack(tmp_path)
    pack = PackLoader().load(root)
    assert pack.provenance.manifest_digest
    assert pack.provenance.file_digests["ok.txt"]


def test_path_escape_rejected(tmp_path: Path) -> None:
    pack = PackLoader().load(_tiny_pack(tmp_path))
    with pytest.raises(InvalidValueError):
        pack.resolve("../etc/passwd")


def test_tampered_file_rejected(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("ok\n", encoding="utf-8")
    manifest = {
        "pack_name": "tiny",
        "files": [{"path": "ok.txt", "sha256": "0" * 64, "bytes": 3}],
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(InvalidValueError):
        PackLoader().load(tmp_path)


def test_missing_manifest_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidValueError):
        PackLoader().load(tmp_path)


def test_explicit_pack_ref_required() -> None:
    with pytest.raises(InvalidValueError):
        PackLoader().load("")


def test_bundle_contains_provenance(tmp_path: Path) -> None:
    root = _tiny_pack(tmp_path)
    # Seed minimal contracts so service can compile against the tiny pack.
    (root / "FINAL_EXECUTION_CONTRACT.yaml").write_text(
        "\n".join(
            [
                "contract_id: FINAL_EXECUTION_CONTRACT",
                "contract_type: universal_execution_contract",
                "source_activation_plan: plan.yaml",
                "terminal_doctrine: terminal.yaml",
                "objective: test",
                "authority_order:",
                "  - user task",
                "kernel_activation:",
                "  - k1",
                "execution_sequence:",
                "  - step",
                "validation_requirements:",
                "  - format",
                "output_contract:",
                "  - summary",
                "adapter_targets:",
                "  - cursor",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(CompileRequest(mission="with pack", pack_root=root))
    assert isinstance(bundle, RuntimeBundle)
    assert bundle.provenance is not None
    assert bundle.provenance.pack_ref == str(root.resolve())
