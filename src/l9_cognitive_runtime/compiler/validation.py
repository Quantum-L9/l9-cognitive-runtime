"""Live validation-contract compilation.

The validation contract is compiled from the live intent, execution contract,
and activation plan. PHASE-06 derives validation properties from execution
obligations; until then the runtime-integrity ladder is the deterministic
single source, and no static ``VALIDATION_CONTRACT.yaml`` is loaded as
fresh-mission truth (INV-009).
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.models import (
    ExecutionContract,
    IntentContract,
    ValidationContract,
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


class ValidationContractCompiler:
    """Compile the live validation contract for a compiled execution."""

    def compile(
        self,
        intent: IntentContract,
        execution: ExecutionContract,
        plan: ActivationPlan,
    ) -> ValidationContract:
        return ValidationContract.from_mapping(
            {
                "contract_id": "VALIDATION_CONTRACT",
                "contract_type": "validation_contract",
                "validation_ladder": list(VALIDATION_LADDER),
                "evidence_required": list(EVIDENCE_REQUIRED),
                "allowed_statuses": [status.value for status in ValidationStatus],
                "report_outputs": list(REPORT_OUTPUTS),
            }
        )
