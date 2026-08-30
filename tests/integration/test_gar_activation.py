"""LIVE-002/003/004: GAR activation evidence, fail-closed absence, and
provenance sensitivity at integration scope."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_cognitive_runtime.models.context import ContextSnapshot
from l9_cognitive_runtime.parsing import StrictParseError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from tests.conftest import discovery_for, governed_signal_snapshot

GAR_REF = "runtime/kernels/architecture/global_architect_kernel.yaml"


def _gar_request(pack: Path) -> CompileRequest:
    return CompileRequest(
        mission="Add safe retry behavior to this asynchronous payment worker.",
        pack_root=pack,
        source_context={"pack": "test"},
    )


# INV-CTX-014: architecture signals are governed facts, not caller hints.
def _gar_snapshot() -> ContextSnapshot:
    return governed_signal_snapshot(
        "message_redelivery_possible",
        "external_side_effect",
        "multiple_workers",
    )


def test_live002_gar_lenses_and_developer_execution(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        _gar_request(valid_pack), context_snapshot=_gar_snapshot()
    )
    assert GAR_REF in bundle.execution.kernel_activation
    assert any(
        ref.endswith("developer_core_kernel.yaml") for ref in bundle.execution.kernel_activation
    )
    evaluators = {p.evaluator for p in bundle.validation.validation_properties}
    assert "idempotency_evidence" in evaluators
    # Lens evidence is recorded at activation time (plan IR).
    from l9_cognitive_runtime.compiler import ActivationPlanner, ObjectiveDeriver

    intent = ObjectiveDeriver().derive(_gar_request(valid_pack))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=(
            valid_pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml"
        ),
        pipeline_path=valid_pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
        discovery=discovery_for(intent, _gar_snapshot()),
    )
    for lens in ("temporal_lens", "failure_lens", "ownership_lens"):
        assert lens in plan.architecture_materiality["active_lenses"]


def test_live003_missing_gar_fails_compile(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    pack = pack_builder(tmp_path / "pack")
    (pack / GAR_REF).unlink()
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    files = [entry for entry in files if entry["path"] != GAR_REF]
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}) + "\n", encoding="utf-8"
    )
    with pytest.raises(StrictParseError):
        CognitiveRuntimeService().compile_runtime(_gar_request(pack))


def test_live004_gar_semantic_change_changes_bundle(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(_gar_request(valid_pack))
    assert bundle.digests()["semantic"]
    assert bundle.execution.metadata is not None
    assert bundle.execution.metadata["kernel_digests"][GAR_REF]
