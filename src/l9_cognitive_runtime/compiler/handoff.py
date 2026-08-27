"""Live handoff-contract compilation.

The handoff contract carries the plan-derived next action, unknowns, and
adapter notes. No static ``HANDOFF_CONTRACT.yaml`` is loaded as fresh-mission
truth (INV-009).
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.models import (
    ExecutionContract,
    HandoffContract,
    IntentContract,
    ValidationContract,
)

LOADED_CONTEXT = [
    "runtime/kernels",
    "runtime/kernel_pipeline",
    "runtime/kernel_pipeline/planner",
    "runtime/contract_compiler",
    "contracts",
]

DECISIONS = [
    "Flawless Victory is terminal doctrine, not Claude-specific format.",
    "Canonical contracts compile before adapter-specific renders.",
    "Adapters render execution intent without owning runtime law.",
]

ADAPTER_NOTES = {
    "claude_code": "repo execution prompt",
    "cursor": "workspace task packet",
    "codex": "dev-kit execution prompt",
    "chatgpt": "handoff/task prompt",
    "human_operator": "runbook checklist",
}


class HandoffContractCompiler:
    """Compile the live handoff contract from the compiled runtime state."""

    def compile(
        self,
        intent: IntentContract,
        execution: ExecutionContract,
        validation: ValidationContract,
        plan: ActivationPlan,
    ) -> HandoffContract:
        if plan.next_phase == "BLOCKED":
            next_action = "BLOCKED: resolve activation blockers before execution."
        else:
            next_action = f"Execute phase {plan.next_phase}."
        return HandoffContract.from_mapping(
            {
                "contract_id": "HANDOFF_CONTRACT",
                "contract_type": "handoff_contract",
                "handoff_summary": (
                    f"Live-compiled handoff: route {plan.matched_route} "
                    f"({plan.confidence} confidence), {len(plan.active_kernels)} active kernels."
                ),
                "loaded_context": list(LOADED_CONTEXT),
                "next_action": next_action,
                "unknowns": list(plan.unknowns),
                "decisions": list(DECISIONS),
                "adapter_notes": dict(ADAPTER_NOTES),
                # A0303: the handoff preserves every unresolved obligation and
                # its current disposition.
                "obligations": [
                    obligation.to_canonical_dict() for obligation in execution.obligations
                ],
            }
        )
