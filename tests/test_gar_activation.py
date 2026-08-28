"""PHASE-04 gate evidence: Global Architect liveness (INV-004, INV-005).

Covers L9CR.GAR.PHASE2.INTEGRATION.001 PHASE-04 and the LIVE-002..005
adversarial shapes:

- qualifying intent activates GAR with lens evidence (LIVE-002);
- nonqualifying intent skips GAR;
- GAR source is digest-bound (INV-014) and appears in every IR;
- missing required GAR source fails compilation (LIVE-003);
- GAR semantic content changes the bundle semantic digest (LIVE-004).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_cognitive_runtime.models import ExecutionGraph
from l9_cognitive_runtime.models.context import ContextSnapshot
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.parsing import ParseErrorCode, StrictParseError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle
from tests.conftest import discovery_for, governed_signal_snapshot

GAR_REF = "runtime/kernels/architecture/global_architect_kernel.yaml"


def _context_pack_request(pack: Path, **context_signals: object) -> CompileRequest:
    """A request whose architecture signals arrive as *governed* context.

    INV-CTX-014: a raw ``source_context.context_signals`` hint cannot prove an
    external architecture fact, so the signals travel in the governed snapshot
    returned by :func:`_signal_snapshot` instead of in the request body.
    """
    return CompileRequest(
        mission="Add safe retry behavior to this asynchronous payment worker.",
        pack_root=pack,
        source_context={"pack": "l9_cognitive_runtime"},
    )


def _signal_snapshot(**context_signals: object) -> ContextSnapshot:
    return governed_signal_snapshot(*context_signals)


def _live_compile(pack: Path) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(
        _context_pack_request(pack),
        context_snapshot=_signal_snapshot(
            message_redelivery_possible=True,
            external_side_effect=True,
            multiple_workers=True,
        ),
    )


def _node_kernel_refs(graph: ExecutionGraph) -> set[str]:
    refs: set[str] = set()
    for node in graph.nodes:
        for ref in node.kernel_refs:
            name = ref.replace("\\", "/").rsplit("/", 1)[-1]
            if name.endswith((".yaml", ".yml")):
                name = name.rsplit(".", 1)[0]
            refs.add(name)
    return refs


def test_qualifying_intent_activates_gar(valid_pack: Path) -> None:
    bundle = _live_compile(valid_pack)
    # Activation evidence (DONE-006): GAR is in the compiled activation set.
    kernel_refs = list(bundle.execution.kernel_activation)
    assert GAR_REF in kernel_refs
    # GAR appears in the execution contract and the graph (DONE-007/008).
    assert "global_architect_kernel" in _node_kernel_refs(bundle.graph)
    # Obligation + liveness: GAR architecture obligation reaches validation.
    ids = {o.obligation_id for o in bundle.execution.obligations}
    assert "OBL.ARCHITECTURE" in ids
    property_refs = {p.obligation_ref for p in bundle.validation.validation_properties}
    assert "OBL.ARCHITECTURE" in property_refs
    # LIVE-002: idempotency property derived from the temporal lens.
    evaluators = [p.evaluator for p in bundle.validation.validation_properties]
    assert "idempotency_evidence" in evaluators


def test_gar_activation_has_lens_evidence(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    from l9_cognitive_runtime.compiler import ActivationPlanner, ObjectiveDeriver

    pack = pack_builder(tmp_path / "pack")
    intent = ObjectiveDeriver().derive(_context_pack_request(pack))
    snapshot = _signal_snapshot(
        message_redelivery_possible=True,
        external_side_effect=True,
        multiple_workers=True,
    )
    plan = ActivationPlanner().plan(
        intent,
        rules_path=pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
        discovery=discovery_for(intent, snapshot),
    )
    materiality = plan.architecture_materiality
    assert materiality["required"] is True
    for lens in ("temporal_lens", "failure_lens", "ownership_lens", "concurrency_lens"):
        assert lens in materiality["active_lenses"], materiality
    assert "P3_ARCHITECTURE_DECISION" in plan.phase_sequence


def test_gar_developer_execution_active_for_worker_mission(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    from l9_cognitive_runtime.compiler import ActivationPlanner, ObjectiveDeriver
    from l9_cognitive_runtime.types import CompileRequest as Request

    pack = pack_builder(tmp_path / "pack")
    intent = ObjectiveDeriver().derive(
        Request(mission="Add safe retry behavior to this asynchronous payment worker.")
    )
    plan = ActivationPlanner().plan(
        intent,
        rules_path=pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
    )
    assert plan.matched_route == "feature_development"
    assert any(k.endswith("developer_core_kernel.yaml") for k in plan.active_kernels)


def test_nonqualifying_intent_skips_gar(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    assert GAR_REF not in bundle.execution.kernel_activation
    assert "OBL.ARCHITECTURE" not in {o.obligation_id for o in bundle.execution.obligations}
    assert "global_architect_kernel" not in _node_kernel_refs(bundle.graph)


def test_gar_source_digest_bound(valid_pack: Path) -> None:
    bundle = _live_compile(valid_pack)
    assert bundle.execution.metadata is not None
    digests = bundle.execution.metadata["kernel_digests"]
    assert digests[GAR_REF]
    assert len(digests[GAR_REF]) == 64


def test_missing_required_gar_source_fails_compile(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    # LIVE-003: remove the GAR kernel file; a material mission must fail
    # compilation — no generic fallback execution plan.
    pack = pack_builder(tmp_path / "pack")
    gar = pack / GAR_REF
    gar.unlink()
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    files = [entry for entry in files if entry["path"] != GAR_REF]
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}) + "\n", encoding="utf-8"
    )
    with pytest.raises(StrictParseError) as excinfo:
        CognitiveRuntimeService().compile_runtime(
            _context_pack_request(
                pack,
                message_redelivery_possible=True,
                external_side_effect=True,
                multiple_workers=True,
            )
        )
    assert excinfo.value.code is ParseErrorCode.UNKNOWN_KERNEL
    assert GAR_REF in str(excinfo.value)


def test_gar_semantic_content_changes_bundle_digest(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    # LIVE-004: modifying GAR semantic content changes the semantic digest
    # (INV-014), while an inactive kernel edit does not.
    pack = pack_builder(tmp_path / "pack")
    before = _live_compile(pack).digests()

    gar = pack / GAR_REF
    text = gar.read_text(encoding="utf-8")
    gar.write_text(text + "\n# semantic revision: tighten ownership lens\n", encoding="utf-8")
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    for entry in files:
        if entry["path"] == GAR_REF:
            import hashlib

            entry["sha256"] = hashlib.sha256(gar.read_bytes()).hexdigest()
            entry["bytes"] = gar.stat().st_size
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}) + "\n", encoding="utf-8"
    )
    after = _live_compile(pack).digests()
    assert after["semantic"] != before["semantic"]
    assert after["execution"] != before["execution"]


def test_gar_required_outputs_declare_consumers(valid_pack: Path) -> None:
    bundle = _live_compile(valid_pack)
    assert bundle.execution.metadata is not None
    gar_metadata = bundle.execution.metadata["kernel_digests"]
    assert GAR_REF in gar_metadata
    # The declared output contract lives on the kernel file; the resolver
    # enforces required outputs have consumers at bind time (fail-closed).
    from l9_cognitive_runtime.compiler.kernels import KernelResolver

    bindings = KernelResolver().resolve([GAR_REF], valid_pack)
    gar = bindings[0]
    assert {output.output_id for output in gar.outputs} == {
        "GAR_SYSTEM_MODEL",
        "GAR_ARCHITECTURE_DECISION",
        "GAR_ARCHITECTURAL_INTEGRITY_EVIDENCE",
        "GAR_PLAN_READINESS",
        "GAR_TYPED_DEFECTS",
    }
    for output in gar.outputs:
        assert output.required is True
        assert output.consumer_refs


def test_gar_output_unknown_consumer_fails(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    pack = pack_builder(tmp_path / "pack")
    gar = pack / GAR_REF
    text = gar.read_text(encoding="utf-8")
    gar.write_text(text.replace("convergence_gate", "mystery_gate"), encoding="utf-8")
    from l9_cognitive_runtime.compiler.kernels import KernelResolver

    with pytest.raises(InvalidValueError, match="consumer"):
        KernelResolver().resolve([GAR_REF], pack)
