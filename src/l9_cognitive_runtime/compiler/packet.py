"""Canonical execution packet (PHASE-07): the immutable, self-contained
projection of a compiled runtime that downstream capable hosts consume.

The packet is the single source adapters project from (A0701) and providers
accept obligations against (A0704). It carries every blocking obligation,
Unknown, validation requirement, delivery requirement, and architectural
constraint — no adapter may weaken it (INV-013).
"""

from __future__ import annotations

from typing import Any

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.models import (
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ObligationDisposition,
    ValidationContract,
)
from l9_cognitive_runtime.models.context import CompiledTaskContext

BLOCK_SEMANTICS = {
    "valid_block_types": ["AUTHORITY", "CAPABILITY", "IRREDUCIBLE_REPOSITORY_CONTRADICTION"],
    "block_evidence_required": True,
}

CONVERGENCE_CONTRACT = {
    "terminal_success_gate": [
        "all_required_obligations_have_legal_disposition",
        "no_required_obligation_is_UNKNOWN",
        "no_blocking_validation_failed",
        "architectural_integrity_satisfied_when_applicable",
        "requested_delivery_satisfied",
        "no_false_completion_condition",
    ],
    "receipt_fields": [
        "terminal_disposition",
        "obligation_dispositions",
        "validation_summary",
        "gate_report",
        "generated_at",
    ],
}


def build_execution_packet(
    *,
    intent: IntentContract,
    kernels: list[KernelBinding],
    plan: ActivationPlan,
    execution: ExecutionContract,
    validation: ValidationContract,
    handoff: HandoffContract,
    graph: ExecutionGraph,
    routing_rules_digest: str,
    pipeline_digest: str,
    semantic_digest: str,
    task_context: CompiledTaskContext,
    context_digest: str,
    context_plan_id: str,
) -> dict[str, Any]:
    """Build the canonical execution packet from compiled IRs."""
    required_obligations = [
        obligation.to_canonical_dict()
        for obligation in execution.obligations
        if obligation.required and obligation.disposition is ObligationDisposition.PENDING
    ]
    delivery_obligations = [
        obligation.to_canonical_dict()
        for obligation in execution.obligations
        if obligation.obligation_id == "OBL.DELIVERY"
    ]
    return {
        "intent": intent.to_canonical_dict(),
        # INV-CTX-030: a lossless canonical copy of the compiled context plus
        # its externally computed digest. Adapters project this; they never
        # rebuild it, and packet validation recomputes the body's digest rather
        # than trusting the declared one.
        "compiled_task_context": task_context.to_canonical_dict(),
        "compiled_task_context_digest": context_digest,
        # INV-CTX-046: downstream consumers can bind execution to the exact
        # demand contract that was recomputed immediately before compilation.
        "context_plan_id": context_plan_id,
        "active_kernel_bindings": [binding.to_dict() for binding in kernels],
        "execution_steps": [step.to_canonical_dict() for step in execution.execution_steps],
        "required_obligations": required_obligations,
        "validation_properties": [
            property.to_canonical_dict() for property in validation.validation_properties
        ],
        "delivery_obligations": delivery_obligations,
        "unknowns": list(intent.unknowns or [])
        + list(plan.unknowns)
        + [unknown.unknown_id for unknown in task_context.unresolved_unknowns],
        "block_semantics": dict(BLOCK_SEMANTICS),
        "convergence_contract": dict(CONVERGENCE_CONTRACT),
        "provenance": {
            "semantic_digest": semantic_digest,
            "routing_rules_digest": routing_rules_digest,
            "pipeline_digest": pipeline_digest,
            "kernel_digests": {binding.source_ref: binding.source_digest for binding in kernels},
            "graph_digest": graph.sha256(),
            "handoff_digest": handoff.sha256(),
            "context_digest": context_digest,
            "context_plan_id": context_plan_id,
        },
    }
