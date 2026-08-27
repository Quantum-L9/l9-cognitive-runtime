"""Terminal success gate and convergence receipt (INV-008, PHASE-06).

Run-level convergence is owned exclusively by the terminal doctrine: the gate
evaluates obligation closure over the execution obligations and validation
properties. No kernel-local metadata may claim run completion (A0604).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from l9_cognitive_runtime.models import (
    ExecutionContract,
    ObligationDisposition,
    ValidationContract,
    ValidationStatus,
)

_LEGAL_TERMINAL = {
    ObligationDisposition.SATISFIED,
    ObligationDisposition.VALID_BLOCK,
    ObligationDisposition.SUPERSEDED_BY_HIGHER_AUTHORITY,
    ObligationDisposition.NOT_APPLICABLE_WITH_DETERMINISTIC_PROOF,
}

_BLOCKING_STATUSES = {
    ValidationStatus.FAILED,
    ValidationStatus.BLOCKED,
    ValidationStatus.UNKNOWN,
    # A required property that never ran cannot be claimed converged.
    ValidationStatus.NOT_RUN,
}


@dataclass(frozen=True)
class TerminalGateReport:
    converged: bool
    unmet: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "converged": self.converged,
            "unmet": list(self.unmet),
            "details": dict(self.details),
        }


def evaluate_terminal_success(
    execution: ExecutionContract,
    validation: ValidationContract,
) -> TerminalGateReport:
    """Evaluate the six-condition terminal success gate, fail closed."""
    unmet: list[str] = []
    details: dict[str, Any] = {}

    required = [o for o in execution.obligations if o.required]
    pending = [o for o in required if o.disposition is ObligationDisposition.PENDING]
    if any(o.disposition not in _LEGAL_TERMINAL for o in required):
        unmet.append("all_required_obligations_have_legal_disposition")
        details["pending_obligations"] = [o.obligation_id for o in pending]
    if pending:
        unmet.append("no_required_obligation_is_UNKNOWN")
        details["unresolved_obligations"] = [o.obligation_id for o in pending]

    blocking_properties = [
        p for p in validation.validation_properties if p.required and p.status in _BLOCKING_STATUSES
    ]
    if blocking_properties:
        unmet.append("no_blocking_validation_failed")
        details["blocking_properties"] = [p.property_id for p in blocking_properties]

    architecture = next(
        (o for o in required if o.obligation_id == "OBL.ARCHITECTURE"), None
    )
    if architecture is not None and architecture.disposition is not ObligationDisposition.PENDING:
        architecture_properties = [
            p
            for p in validation.validation_properties
            if p.obligation_ref == "OBL.ARCHITECTURE" and p.required
        ]
        if any(p.status is not ValidationStatus.PASSED for p in architecture_properties):
            unmet.append("architectural_integrity_satisfied_when_applicable")
            details["architecture_property_statuses"] = [
                (p.property_id, p.status.value) for p in architecture_properties
            ]

    delivery = next((o for o in required if o.obligation_id == "OBL.DELIVERY"), None)
    if delivery is not None and delivery.disposition is not ObligationDisposition.SATISFIED:
        unmet.append("requested_delivery_satisfied")
        details["delivery_disposition"] = delivery.disposition.value

    if unmet:
        unmet.append("no_false_completion_condition")

    return TerminalGateReport(converged=not unmet, unmet=tuple(unmet), details=details)


def convergence_receipt(report: TerminalGateReport, execution: ExecutionContract) -> dict[str, Any]:
    """Generate the terminal receipt from the gate report and dispositions."""
    return {
        "terminal_disposition": "CONVERGED" if report.converged else "NOT_CONVERGED",
        "obligation_dispositions": {
            o.obligation_id: o.disposition.value for o in execution.obligations
        },
        "gate_report": report.to_dict(),
    }
