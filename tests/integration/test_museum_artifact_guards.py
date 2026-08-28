"""MUSEUM-001..010: every museum-artifact detector must pass — no required
kernel is inert, no output unconsumed, no static fixture authoritative."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.obligations import conserve
from l9_cognitive_runtime.models.errors import ModelValidationError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle

GAR_REF = "runtime/kernels/architecture/global_architect_kernel.yaml"


def _gar_bundle(pack: Path) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(
        CompileRequest(
            mission="Add safe retry behavior to this asynchronous payment worker.",
            pack_root=pack,
            source_context={
                "pack": "test",
                "context_signals": [
                    "message_redelivery_possible",
                    "external_side_effect",
                    "multiple_workers",
                ],
            },
        )
    )


def test_museum001_required_kernel_activates(valid_pack: Path) -> None:
    bundle = _gar_bundle(valid_pack)
    assert GAR_REF in bundle.execution.kernel_activation


def test_museum002_activated_kernel_has_graph_node(valid_pack: Path) -> None:
    bundle = _gar_bundle(valid_pack)
    refs = {ref for node in bundle.graph.nodes for ref in node.kernel_refs}
    assert GAR_REF in refs


def test_museum003_graph_kernel_declares_outputs(valid_pack: Path) -> None:
    gar = KernelResolver().resolve([GAR_REF], valid_pack)[0]
    assert {o.output_id for o in gar.outputs} == {
        "GAR_SYSTEM_MODEL",
        "GAR_ARCHITECTURE_DECISION",
        "GAR_ARCHITECTURAL_INTEGRITY_EVIDENCE",
        "GAR_PLAN_READINESS",
        "GAR_TYPED_DEFECTS",
    }


def test_museum004_kernel_outputs_have_consumers(valid_pack: Path) -> None:
    gar = KernelResolver().resolve([GAR_REF], valid_pack)[0]
    for output in gar.outputs:
        assert output.consumer_refs


def test_museum005_outputs_reach_gates(valid_pack: Path) -> None:
    bundle = _gar_bundle(valid_pack)
    evaluators = {p.evaluator for p in bundle.validation.validation_properties}
    assert "architecture_integrity_evidence" in evaluators
    assert "idempotency_evidence" in evaluators


def test_museum006_gar_change_changes_semantics(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    import hashlib

    pack = pack_builder(tmp_path / "pack")
    before = _gar_bundle(pack).digests()
    gar = pack / GAR_REF
    text = gar.read_text(encoding="utf-8")
    gar.write_text(text + "\n# semantic revision\n", encoding="utf-8")
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    for entry in files:
        if entry["path"] == GAR_REF:
            entry["sha256"] = hashlib.sha256(gar.read_bytes()).hexdigest()
            entry["bytes"] = gar.stat().st_size
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}) + "\n", encoding="utf-8"
    )
    after = _gar_bundle(pack).digests()
    assert after["semantic"] != before["semantic"]


def test_museum007_distinct_realizations_differ(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    audit = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    fix = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    assert audit.digests()["execution"] != fix.digests()["execution"]
    assert audit.digests()["graph"] != fix.digests()["graph"]
    assert audit.digests()["semantic"] != fix.digests()["semantic"]


def test_museum008_public_surfaces_use_live_compiler(  # type: ignore[no-untyped-def]
    tmp_path: Path, valid_pack: Path, capsys
) -> None:
    from l9_cognitive_runtime.cli import main as cli_main

    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    assert cli_main(["--mission", "Audit this repository.", "--pack-root", str(valid_pack)]) == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["digests"] == bundle.digests()


def test_museum009_obligation_cannot_disappear(valid_pack: Path) -> None:
    bundle = _gar_bundle(valid_pack)
    dropped = [o for o in bundle.execution.obligations if o.obligation_id != "OBL.ARCHITECTURE"]
    with pytest.raises(ModelValidationError, match="disappeared"):
        conserve(bundle.intent.obligations, dropped, stage="intent->execution")


def test_museum010_static_fixture_never_authoritative(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    # A pack with NO static FINAL_EXECUTION_CONTRACT.yaml compiles identically
    # to the same pack carrying one: the static fixture has no authority.
    bare = pack_builder(tmp_path / "bare", execution=None)
    laden = pack_builder(tmp_path / "laden")
    service = CognitiveRuntimeService()
    mission = "Audit this repository."
    bare_bundle = service.compile_runtime(CompileRequest(mission=mission, pack_root=bare))
    laden_bundle = service.compile_runtime(CompileRequest(mission=mission, pack_root=laden))
    assert bare_bundle.digests() == laden_bundle.digests()
