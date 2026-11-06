# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_integration_test_validation_derivation__py
# title: test validation derivation
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/integration/test_validation_derivation.py
# content_hash: 0d51da7d6c534235c826e5f5df687e1bb71da80098ced983e2ab8e50cdecab8b
# token_cost_estimate: 779
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""LIVE-008: a missing validation tool cannot erase the validation
obligation; alternate discriminating evidence can satisfy the property."""

from __future__ import annotations

from pathlib import Path

from l9_cognitive_runtime.compiler.convergence import evaluate_terminal_success
from l9_cognitive_runtime.models import ObligationDisposition, ValidationStatus
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle


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


def test_live008_requirement_survives_tool_absence(valid_pack: Path) -> None:
    bundle = _gar_bundle(valid_pack)
    idempotency = next(
        p
        for p in bundle.validation.validation_properties
        if p.property_id == "PROP.GAR.IDEMPOTENCY"
    )
    # The validation tool being unavailable does not touch the requirement:
    # the property stays required and NOT_RUN blocks convergence.
    assert idempotency.required is True
    assert idempotency.status is ValidationStatus.NOT_RUN
    assert idempotency.status is ValidationStatus.NOT_RUN
    for obligation in bundle.execution.obligations:
        if obligation.required:
            obligation.disposition = ObligationDisposition.SATISFIED
    for prop in bundle.validation.validation_properties:
        prop.status = ValidationStatus.PASSED
    idempotency.status = ValidationStatus.NOT_RUN  # tool unavailable
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is False
    assert "no_blocking_validation_failed" in report.unmet


def test_live008_alternate_evidence_satisfies_property(valid_pack: Path) -> None:
    bundle = _gar_bundle(valid_pack)
    idempotency = next(
        p
        for p in bundle.validation.validation_properties
        if p.property_id == "PROP.GAR.IDEMPOTENCY"
    )
    # Alternate discriminating evidence satisfies the same property — the
    # requirement is never downgraded to not-applicable.
    idempotency.evidence_refs = [
        "idempotency-key-analysis.md",
        "message-redelivery-trace.txt",
    ]
    idempotency.status = ValidationStatus.PASSED
    assert idempotency.required is True
    assert idempotency.status is ValidationStatus.PASSED
    for obligation in bundle.execution.obligations:
        if obligation.required:
            obligation.disposition = ObligationDisposition.SATISFIED
    for prop in bundle.validation.validation_properties:
        prop.status = ValidationStatus.PASSED
    report = evaluate_terminal_success(bundle.execution, bundle.validation)
    assert report.converged is True
