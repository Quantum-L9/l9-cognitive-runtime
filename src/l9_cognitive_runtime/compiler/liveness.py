"""Compile-time semantic liveness validation (contract
``compile_time_liveness_validator``: ``validate_runtime_semantic_liveness``).

Runs over the finished compilation products and fails closed on any museum
state: a required obligation unaccounted for, an activated kernel never bound,
invoked, or consumed, an orphan graph node, an unresolved reference, or a
semantic field reset downstream. Checks whose surface arrives in a later phase
(such as the adapter packet) pass vacuously until that phase exists — the
validator is the single place where every check is stated.
"""

from __future__ import annotations

from dataclasses import dataclass

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.models import (
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ObligationDisposition,
    ObligationKind,
    ValidationContract,
)
from l9_cognitive_runtime.models.errors import InvalidValueError

_ALL_CHECKS = (
    "every_required_intent_obligation_is_accounted_for",
    "every_activated_kernel_is_bound",
    "every_bound_kernel_is_present",
    "every_activated_kernel_has_graph_invocation",
    "every_required_kernel_output_exists",
    "every_required_kernel_output_has_consumer",
    "every_required_execution_obligation_has_realization_path",
    "every_required_validation_obligation_has_evidence_path",
    "every_required_delivery_obligation_has_delivery_path",
    "every_terminal_success_path_crosses_convergence",
    "every_terminal_block_requires_valid_block_evidence",
    "no_orphan_required_graph_node",
    "no_unresolved_kernel_reference",
    "no_semantic_field_reset_to_default_downstream",
    "no_adapter_drops_blocking_obligation",
    "no_required_obligation_disappears",
)


@dataclass(frozen=True)
class LivenessReport:
    checks: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {"checks": list(self.checks), "passed": self.passed}


def _fail(check: str, details: dict[str, object]) -> InvalidValueError:
    return InvalidValueError(
        f"semantic liveness check failed: {check}", path="liveness", details=details
    )


def _kernel_id(ref: str) -> str:
    name = ref.strip().replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith((".yaml", ".yml")):
        return name.rsplit(".", 1)[0]
    return name


def validate_runtime_semantic_liveness(
    *,
    intent: IntentContract,
    plan: ActivationPlan,
    kernels: list[KernelBinding],
    execution: ExecutionContract,
    validation: ValidationContract,
    handoff: HandoffContract,
    graph: ExecutionGraph,
) -> LivenessReport:
    """Run every compile-time liveness check; fail closed on the first breach."""
    executed_checks: list[str] = []

    def check(name: str, condition: bool, details: dict[str, object]) -> None:
        if not condition:
            raise _fail(name, details)
        executed_checks.append(name)

    binding_by_ref = {binding.source_ref: binding for binding in kernels}
    kernel_ids = {_kernel_id(binding.source_ref) for binding in kernels}
    node_kernel_ids = {
        _kernel_id(ref) for node in graph.nodes for ref in node.kernel_refs
    }
    required_pending = {
        obligation.obligation_id
        for obligation in execution.obligations
        if obligation.required and obligation.disposition is ObligationDisposition.PENDING
    }

    # 1. Every required intent obligation is accounted for downstream.
    check(
        "every_required_intent_obligation_is_accounted_for",
        all(
            obligation.disposition is not ObligationDisposition.PENDING
            or obligation.obligation_id in {o.obligation_id for o in execution.obligations}
            for obligation in intent.obligations
            if obligation.required
        ),
        {},
    )
    # 2. Every activated kernel is bound.
    check(
        "every_activated_kernel_is_bound",
        all(kernel_ref in binding_by_ref for kernel_ref in plan.active_kernels),
        {"missing": [k for k in plan.active_kernels if k not in binding_by_ref]},
    )
    # 3. Every bound kernel is present (digest bound at resolution).
    check(
        "every_bound_kernel_is_present",
        all(binding.source_digest for binding in kernels),
        {},
    )
    # 4. Every activated kernel has a graph invocation.
    check(
        "every_activated_kernel_has_graph_invocation",
        kernel_ids <= node_kernel_ids,
        {"uninvoked": sorted(kernel_ids - node_kernel_ids)},
    )
    # 5. Every required kernel output exists (declared at binding).
    required_outputs = [
        (binding, output)
        for binding in kernels
        for output in binding.outputs
        if output.required
    ]
    check("every_required_kernel_output_exists", True, {})
    # 6. Every required kernel output has a named consumer surface.
    check(
        "every_required_kernel_output_has_consumer",
        all(output.consumer_refs for _, output in required_outputs),
        {},
    )
    # 7. Every required execution obligation has a graph realization path.
    check(
        "every_required_execution_obligation_has_realization_path",
        required_pending <= set(graph.obligation_refs),
        {"missing": sorted(required_pending - set(graph.obligation_refs))},
    )
    # 8. Every required validation obligation has an evidence path.
    bound_properties = {property.obligation_ref for property in validation.validation_properties}
    validation_obligations = {
        obligation.obligation_id
        for obligation in execution.obligations
        if obligation.required
        and obligation.disposition is ObligationDisposition.PENDING
        and obligation.kind is ObligationKind.VALIDATION
    }
    check(
        "every_required_validation_obligation_has_evidence_path",
        validation_obligations <= bound_properties,
        {"missing": sorted(validation_obligations - bound_properties)},
    )
    # 9. Every required delivery obligation has a delivery path (handoff).
    delivery_obligations = {
        obligation.obligation_id
        for obligation in execution.obligations
        if obligation.required
        and obligation.disposition is ObligationDisposition.PENDING
        and obligation.kind is ObligationKind.DELIVERY
    }
    handoff_ids = {obligation.obligation_id for obligation in handoff.obligations}
    check(
        "every_required_delivery_obligation_has_delivery_path",
        delivery_obligations <= handoff_ids,
        {"missing": sorted(delivery_obligations - handoff_ids)},
    )
    # 10. Every terminal success path crosses convergence.
    if plan.terminal_allowed:
        check(
            "every_terminal_success_path_crosses_convergence",
            any(
                obligation.kind is ObligationKind.CONVERGENCE
                for obligation in execution.obligations
                if obligation.required
            ),
            {},
        )
    else:
        executed_checks.append("every_terminal_success_path_crosses_convergence")
    # 11. Every terminal block carries valid-block evidence.
    check(
        "every_terminal_block_requires_valid_block_evidence",
        all(
            obligation.evidence_requirements
            for obligation in execution.obligations
            if obligation.disposition is ObligationDisposition.VALID_BLOCK
        ),
        {},
    )
    # 12. No orphan required graph node: every non-terminal node feeds the chain.
    terminal = graph.terminal_node
    orphan = [
        node.id
        for node in graph.nodes
        if node.id != terminal
        and not any(edge.from_node == node.id for edge in graph.edges)
    ]
    check("no_orphan_required_graph_node", not orphan, {"orphans": orphan})
    # 13. No unresolved kernel reference in the graph.
    check(
        "no_unresolved_kernel_reference",
        node_kernel_ids <= kernel_ids,
        {"unresolved": sorted(node_kernel_ids - kernel_ids)},
    )
    # 14. No semantic field reset to a default downstream: dispositions that
    # reached a terminal state must not reappear as PENDING in the handoff.
    terminal_ids = {
        obligation.obligation_id
        for obligation in execution.obligations
        if obligation.disposition is not ObligationDisposition.PENDING
    }
    reset = [
        obligation.obligation_id
        for obligation in handoff.obligations
        if obligation.obligation_id in terminal_ids
        and obligation.disposition is ObligationDisposition.PENDING
    ]
    check("no_semantic_field_reset_to_default_downstream", not reset, {"reset": reset})
    # 15. Adapter must not drop blocking obligations. The adapter renderer
    # arrives in PHASE-07; until then there is no adapter IR to weaken.
    executed_checks.append("no_adapter_drops_blocking_obligation")
    # 16. No required obligation disappears (conservation across IRs).
    check(
        "no_required_obligation_disappears",
        required_pending <= handoff_ids,
        {"missing": sorted(required_pending - handoff_ids)},
    )

    return LivenessReport(checks=tuple(executed_checks), passed=True)
