"""Live validation-contract compilation.

The validation contract is compiled from the live intent, execution contract,
and activation plan. Validation properties are bound one-to-one to the
required pending execution obligations (A0302): every blocking obligation has
an evaluator and an evidence type, and no property may reference an obligation
the execution contract does not carry. No static ``VALIDATION_CONTRACT.yaml``
is loaded as fresh-mission truth (INV-009).
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.models import (
    ExecutionContract,
    IntentContract,
    ObligationKind,
    ValidationContract,
    ValidationProperty,
    ValidationStatus,
)

VALIDATION_LADDER = [
    "format",
    "schema",
    "pipeline_order",
    "kernel_roles",
    "duplicate_active_kernel_scan",
    "activation_planner",
    "contract_compiler",
    "adapter_render",
    "evidence_manifest",
]

EVIDENCE_REQUIRED = [
    "command run or blocker reason",
    "validator name",
    "status",
    "findings",
    "timestamp or report path",
]

REPORT_OUTPUTS = [
    "runtime/kernel_pipeline/KERNEL_PIPELINE_VALIDATION_REPORT.json",
    "VALIDATION_EVIDENCE.md",
]

_EVALUATOR_BY_KIND = {
    ObligationKind.REALIZATION: "realization_evidence",
    ObligationKind.ARCHITECTURE: "architecture_integrity_evidence",
    ObligationKind.VALIDATION: "validation_ladder",
    ObligationKind.DELIVERY: "delivery_evidence",
    ObligationKind.AUTHORITY: "authority_order",
    ObligationKind.EPISTEMIC: "unknown_resolution",
    ObligationKind.CONVERGENCE: "terminal_success_gate",
}


class ValidationContractCompiler:
    """Compile the live validation contract for a compiled execution."""

    def compile(
        self,
        intent: IntentContract,
        execution: ExecutionContract,
        plan: ActivationPlan,
    ) -> ValidationContract:
        properties: list[ValidationProperty] = []
        for obligation in execution.obligations:
            if not obligation.required:
                continue
            properties.append(
                ValidationProperty(
                    property_id=f"PROP.{obligation.obligation_id}",
                    obligation_ref=obligation.obligation_id,
                    evaluator=_EVALUATOR_BY_KIND[obligation.kind],
                    evidence_type="evidence_manifest",
                    required=True,
                    status=ValidationStatus.NOT_RUN,
                )
            )
        return ValidationContract.from_mapping(
            {
                "contract_id": "VALIDATION_CONTRACT",
                "contract_type": "validation_contract",
                "validation_ladder": list(VALIDATION_LADDER),
                "evidence_required": list(EVIDENCE_REQUIRED),
                "allowed_statuses": [status.value for status in ValidationStatus],
                "report_outputs": list(REPORT_OUTPUTS),
                "validation_properties": [
                    property.to_canonical_dict() for property in properties
                ],
            }
        )
