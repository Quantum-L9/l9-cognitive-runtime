"""PHASE-06 gate evidence: validation & convergence derivation (INV-007/008).

Covers L9CR.GAR.PHASE2.INTEGRATION.001 PHASE-06:

- A0601: runtime-integrity validation split from objective validation;
- A0602: objective validation derives from intent/execution obligations;
- A0603: terminal doctrine owns convergence evaluation + receipt only;
- A0604: kernel-local metadata cannot claim run-level convergence.
- Terminal success gate: obligation closure, no UNKNOWN, no blocking
  failures, architectural integrity, delivery, no false completion.
"""

from __future__ import annotations

from pathlib import Path

from l9_cognitive_runtime.compiler.convergence import (
    convergence_receipt,
    evaluate_terminal_success,
)
from l9_cognitive_runtime.models import (
    ObligationDisposition,
    ValidationStatus,
)
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle


def _bundle(pack: Path, mission: str) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission=mission, pack_root=pack)
    )


def test_runtime_integrity_split_from_objective_validation(valid_pack: Path) -> None:
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    ids = {o.obligation_id for o in bundle.execution.obligations}
    assert "OBL.RUNTIME_INTEGRITY" in ids
    assert "OBL.VALIDATION" in ids
    properties = bundle.validation.validation_properties
    by_evaluator = {p.evaluator for p in properties}
    # The ladder evaluates runtime integrity; objective properties use their
    # kind-specific evaluators.
    assert "validation_ladder" in by_evaluator
    assert "realization_evidence" in by_evaluator
    assert "delivery_evidence" in by_evaluator


def test_validation_derives_from_objective_semantics(valid_pack: Path) -> None:
    audit = _bundle(valid_pack, "Audit this repository.")
    fix = _bundle(valid_pack, "Audit and fix this repository.")
    assert audit.validation.sha256() != fix.validation.sha256()
    audit_refs = {p.obligation_ref for p in audit.validation.validation_properties}
    fix_refs = {p.obligation_ref for p in fix.validation.validation_properties}
    assert "OBL.DELIVERY" not in audit_refs
    assert "OBL.DELIVERY" in fix_refs


def test_delivery_obligation_reaches_validation(valid_pack: Path) -> None:
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    delivery_props = [
        p for p in bundle.validation.validation_properties if p.obligation_ref == "OBL.DELIVERY"
    ]
    assert delivery_props
    assert delivery_props[0].evaluator == "delivery_evidence"
    assert delivery_props[0].required is True


def test_terminal_success_requires_obligation_closure(valid_pack: Path) -> None:
    # A freshly compiled bundle is NOT converged: obligations are pending and
    # properties not run. Closure is required — the gate fails closed.
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is False
    assert "all_required_obligations_have_legal_disposition" in report.unmet
    assert "no_required_obligation_is_UNKNOWN" in report.unmet
    assert "no_false_completion_condition" in report.unmet


def test_terminal_success_converged_when_closed(valid_pack: Path) -> None:
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    for obligation in bundle.execution.obligations:
        if obligation.required:
            obligation.disposition = ObligationDisposition.SATISFIED
    for prop in bundle.validation.validation_properties:
        prop.status = ValidationStatus.PASSED
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is True
    receipt = convergence_receipt(report, bundle.execution)
    assert receipt["terminal_disposition"] == "CONVERGED"
    assert set(receipt["obligation_dispositions"].values()) == {"SATISFIED"}


def test_blocking_validation_prevents_convergence(valid_pack: Path) -> None:
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    for obligation in bundle.execution.obligations:
        if obligation.required:
            obligation.disposition = ObligationDisposition.SATISFIED
    for prop in bundle.validation.validation_properties:
        prop.status = ValidationStatus.PASSED
    blocking = next(
        p for p in bundle.validation.validation_properties if p.obligation_ref == "OBL.REALIZATION"
    )
    blocking.status = ValidationStatus.FAILED
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is False
    assert "no_blocking_validation_failed" in report.unmet


def test_architecture_integrity_required_when_gar_active(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    from l9_cognitive_runtime.service import CognitiveRuntimeService as Service

    pack = pack_builder(tmp_path / "pack")
    bundle = Service().compile_runtime(
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
    assert "OBL.ARCHITECTURE" in {o.obligation_id for o in bundle.execution.obligations}
    for obligation in bundle.execution.obligations:
        if obligation.required:
            obligation.disposition = ObligationDisposition.SATISFIED
    for prop in bundle.validation.validation_properties:
        prop.status = ValidationStatus.PASSED
    architecture_props = [
        p for p in bundle.validation.validation_properties if p.obligation_ref == "OBL.ARCHITECTURE"
    ]
    for prop in architecture_props:
        prop.status = ValidationStatus.NOT_RUN
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is False
    assert "architectural_integrity_satisfied_when_applicable" in report.unmet


def test_delivery_must_be_satisfied_for_convergence(valid_pack: Path) -> None:
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    for obligation in bundle.execution.obligations:
        if obligation.required:
            disposition = (
                ObligationDisposition.SATISFIED
                if obligation.obligation_id != "OBL.DELIVERY"
                else ObligationDisposition.PENDING
            )
            obligation.disposition = disposition
    for prop in bundle.validation.validation_properties:
        prop.status = ValidationStatus.PASSED
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is False
    assert "requested_delivery_satisfied" in report.unmet


def test_kernel_local_metadata_never_claims_run_convergence(valid_pack: Path) -> None:
    # A0604: the graph's CONVERGED disposition exists only on a terminal
    # (P7) node; a non-terminal run has no convergence claim anywhere.
    bundle = _bundle(valid_pack, "Audit and fix this repository.")
    assert bundle.graph.terminal_disposition is None
    assert all(node.disposition is None for node in bundle.graph.nodes)
    # The terminal gate reads only obligations + validation properties — no
    # kernel-local metadata participates.
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is False


def test_terminal_kernel_contract_retains_convergence_semantics() -> None:
    """A0603: the terminal kernel owns convergence evaluation and receipts,
    not duplicated outcome-accountability semantics."""
    from pathlib import Path as _Path

    import yaml

    kernel_path = (
        _Path(__file__).resolve().parents[1]
        / "runtime"
        / "kernels"
        / "terminal"
        / "flawless_victory.contract.yaml"
    )
    text = kernel_path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    gate = doc["contract"]["terminal_success_gate"]
    assert "all_required_obligations_have_legal_disposition" in gate
    assert "no_false_completion_condition" in gate
    receipt_fields = doc["contract"]["receipt"]["fields"]
    assert "obligation_dispositions" in receipt_fields
    assert "gate_report" in receipt_fields
    # The duplicated outcome-accountability semantics are gone.
    assert "convergence_reached" not in text
    assert "objective" not in doc["contract"]
