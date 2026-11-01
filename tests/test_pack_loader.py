"""Tamper, traversal, and provenance tests for PackLoader."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest, RuntimeBundle
from tests.conftest import write_manifest


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
    # The live spine resolves routing rules, the pipeline definition, and
    # activated kernels from the pack; copy the runtime tree in. Every source
    # the compiler consumes must be manifest-listed (RU-03), so the manifest
    # is rewritten over the completed pack before compiling.
    repo_root = Path(__file__).resolve().parents[1]
    for src in (repo_root / "runtime").rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(repo_root).as_posix()
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    kernel = root / "runtime" / "kernels" / "task" / "k1.yaml"
    kernel.parent.mkdir(parents=True, exist_ok=True)
    kernel.write_text("id: k1\n", encoding="utf-8")
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
                "  - runtime/kernels/task/k1.yaml",
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
    (root / "VALIDATION_CONTRACT.yaml").write_text(
        "\n".join(
            [
                "contract_id: VALIDATION_CONTRACT",
                "contract_type: validation_contract",
                "validation_ladder:",
                "  - format",
                "evidence_required:",
                "  - status",
                "allowed_statuses:",
                "  - passed",
                "  - failed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "HANDOFF_CONTRACT.yaml").write_text(
        "\n".join(
            [
                "contract_id: HANDOFF_CONTRACT",
                "contract_type: handoff_contract",
                "handoff_summary: test",
                "loaded_context:",
                "  - runtime/kernels",
                "next_action: continue",
                "unknowns: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_manifest(root)
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(CompileRequest(mission="with pack", pack_root=root))
    assert isinstance(bundle, RuntimeBundle)
    assert bundle.provenance.pack_ref == str(root.resolve())


def test_unlisted_activated_kernel_fails_compile_naming_it(
    tmp_path: Path, pack_builder: Callable[..., Path]
) -> None:
    """RG-003a: a kernel the manifest does not list is never read as verified.

    The file stays on disk; only its manifest entry is gone. Verification is a
    property of the bytes the compiler consumes, so an unlisted kernel must
    fail closed with a typed error naming it and produce no bundle.
    """
    pack = pack_builder(tmp_path / "pack")
    request = CompileRequest(mission="Audit this repository.", pack_root=pack)
    kernel = CognitiveRuntimeService().compile_runtime(request).execution.kernel_activation[0]
    assert (pack / kernel).is_file()
    manifest = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != kernel]
    (pack / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(InvalidValueError) as excinfo:
        CognitiveRuntimeService().compile_runtime(request)
    assert excinfo.value.path == kernel
    assert kernel in str(excinfo.value)


def test_packet_kernel_digests_equal_the_manifest_digests(valid_pack: Path) -> None:
    """Every recorded kernel digest is the manifest-verified digest (RU-03)."""
    pack = PackLoader().load(valid_pack)
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    recorded = bundle.packet["provenance"]["kernel_digests"]
    assert recorded
    assert recorded == {ref: pack.provenance.file_digests[ref] for ref in recorded}
    assert bundle.context_plan is not None
    assert bundle.context_plan.active_kernel_digests == recorded
