"""Compile-time semantic liveness validation (contract
``compile_time_liveness_validator``: ``validate_runtime_semantic_liveness``).

Runs over the finished compilation products and fails closed on any museum
state: a required obligation unaccounted for, an activated kernel never bound,
invoked, or consumed, a required kernel output never realized, an orphan graph
node, an unresolved reference, a semantic field reset downstream, an execution
packet that drops a blocking obligation, or a compiled context whose identity
did not survive into the packet.

Two rules govern this module and are the reason it looks the way it does.

**Every declared check must actually execute.** Coverage is asserted before the
report is returned, so a declared-but-skipped check can never report a
guarantee that was never evaluated.

**Every check must compute something.** Appending a name without evaluating a
condition, writing a literal-``True`` condition, restating the declaration the
check is meant to verify, or making an input optional so the check can be
skipped when it is absent — all four produce a passing report that means
nothing. Every input here is therefore required, and every condition is derived
from the compiled artifacts (INV-CTX-039).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.context_closure import CONTEXT_CHECKS, ContextClosureReport
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
from l9_cognitive_runtime.models.context import (
    GOVERNED_LEVELS,
    CompiledTaskContext,
    UnknownMateriality,
    UnknownReasonCode,
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
    # Context-native semantic liveness (INV-CTX-039).
    "context_closure_ladder_executed_completely",
    "every_authoritative_selected_item_has_provenance",
    "every_selected_context_item_has_relevance_binding",
    "every_selected_kernel_equals_downstream_kernel_binding",
    "no_unresolved_equal_authority_conflict_is_silently_selected",
    "context_digest_participates_in_semantic_identity",
    "execution_packet_preserves_compiled_context",
    "material_context_unknowns_are_conserved",
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
    task_context: CompiledTaskContext,
    context_digest: str,
    closure_report: ContextClosureReport,
    packet: dict[str, Any],
    semantic_payload: dict[str, Any],
) -> LivenessReport:
    """Run every compile-time liveness check; fail closed on the first breach.

    Every parameter is required. A validator that silently skips a check when an
    input is absent is the museum state this validator exists to detect, so
    there is deliberately no optional surface to skip on.
    """
    executed_checks: list[str] = []

    def check(name: str, condition: bool, details: dict[str, object]) -> None:
        if not condition:
            raise _fail(name, details)
        executed_checks.append(name)

    binding_by_ref = {binding.source_ref: binding for binding in kernels}
    kernel_ids = {_kernel_id(binding.source_ref) for binding in kernels}
    node_kernel_ids = {_kernel_id(ref) for node in graph.nodes for ref in node.kernel_refs}
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
    # 5. Every required kernel output is actually realized. Not "was declared" —
    # that is the declaration this check exists to verify against reality. The
    # output must appear on an execution step that invokes the declaring kernel,
    # and must survive the graph projection of that same step, since the graph
    # carries the same output contract and derivation is not proof.
    required_outputs = [
        (binding, output) for binding in kernels for output in binding.outputs if output.required
    ]
    step_outputs: dict[str, set[str]] = {}
    for step in execution.execution_steps:
        for ref in step.kernel_refs:
            step_outputs.setdefault(ref, set()).update(step.output_refs)
    graph_outputs: dict[str, set[str]] = {}
    for node in graph.nodes:
        for ref in node.kernel_refs:
            graph_outputs.setdefault(ref, set()).update(node.outputs)
    unrealized: list[dict[str, str]] = []
    for binding, output in required_outputs:
        if output.output_id not in step_outputs.get(binding.source_ref, set()):
            unrealized.append(
                {
                    "kernel": binding.source_ref,
                    "output": output.output_id,
                    "surface": "execution_step",
                }
            )
        elif output.output_id not in graph_outputs.get(binding.source_ref, set()):
            unrealized.append(
                {
                    "kernel": binding.source_ref,
                    "output": output.output_id,
                    "surface": "graph_node",
                }
            )
    check("every_required_kernel_output_exists", not unrealized, {"unrealized": unrealized})
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
    # 8. Every required validation obligation has an evidence path; GAR
    # architecture obligations reach validation too (DONE-010).
    bound_properties = {property.obligation_ref for property in validation.validation_properties}
    evidence_bound_obligations = {
        obligation.obligation_id
        for obligation in execution.obligations
        if obligation.required
        and obligation.disposition is ObligationDisposition.PENDING
        and obligation.kind in {ObligationKind.VALIDATION, ObligationKind.ARCHITECTURE}
    }
    check(
        "every_required_validation_obligation_has_evidence_path",
        evidence_bound_obligations <= bound_properties,
        {"missing": sorted(evidence_bound_obligations - bound_properties)},
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
        # No terminal phase was activated, so the property holds by absence —
        # and that absence is itself the computed condition, not an assumption.
        check(
            "every_terminal_success_path_crosses_convergence",
            not any(step.phase == "P7_FLAWLESS_VICTORY" for step in execution.execution_steps),
            {"terminal_allowed": False},
        )
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
        if node.id != terminal and not any(edge.from_node == node.id for edge in graph.edges)
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
    # 15. The execution packet is the hand-off projection every downstream
    # provider consumes (INV-013, A0702). A required blocking obligation that
    # does not survive into it is a silently weakened contract.
    packet_required = {
        str(entry.get("obligation_id")) for entry in (packet.get("required_obligations") or [])
    }
    dropped = required_pending - packet_required
    check(
        "no_adapter_drops_blocking_obligation",
        not dropped,
        {"dropped": sorted(dropped)},
    )
    # 16. No required obligation disappears (conservation across IRs).
    check(
        "no_required_obligation_disappears",
        required_pending <= handoff_ids,
        {"missing": sorted(required_pending - handoff_ids)},
    )

    # ------------------------------------------------------------------
    # Context-native semantic liveness (INV-CTX-039).
    # ------------------------------------------------------------------
    selected = task_context.selected_items()
    # 17. Context closure ran, passed, and ran its whole ladder. Closure proved
    # each requirement item by item; liveness proves closure itself did not
    # quietly report a shorter ladder.
    check(
        "context_closure_ladder_executed_completely",
        closure_report.passed and closure_report.checks == CONTEXT_CHECKS,
        {"closure_report": closure_report.to_dict(), "expected": list(CONTEXT_CHECKS)},
    )
    # 18. Governed claims carry immutable provenance.
    unprovenanced = [
        item.item_id
        for item in selected
        if item.authority_level in GOVERNED_LEVELS and not item.source_ref.has_immutable_provenance
    ]
    check(
        "every_authoritative_selected_item_has_provenance",
        not unprovenanced,
        {"item_ids": unprovenanced},
    )
    # 19. Nothing sits in the context without a reason it is there.
    unbound = [item.item_id for item in selected if not item.selected_because]
    check("every_selected_context_item_has_relevance_binding", not unbound, {"item_ids": unbound})
    # 20. INV-CTX-020: context kernels are the bindings used downstream.
    check(
        "every_selected_kernel_equals_downstream_kernel_binding",
        task_context.selected_kernels == [binding.to_dict() for binding in kernels],
        {"context": len(task_context.selected_kernels), "downstream": len(kernels)},
    )
    # 21. A contradiction that reached the context is visible as an Unknown and
    # never also selected.
    conflict_keys = {
        unknown.semantic_key
        for unknown in task_context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS
        and unknown.semantic_key
    }
    selected_conflicts = sorted(
        {item.semantic_key for item in selected if item.semantic_key in conflict_keys}
    )
    check(
        "no_unresolved_equal_authority_conflict_is_silently_selected",
        not selected_conflicts,
        {"semantic_keys": selected_conflicts},
    )
    # 22. INV-CTX-029: the context digest is part of runtime semantic identity.
    check(
        "context_digest_participates_in_semantic_identity",
        semantic_payload.get("context_digest") == context_digest
        and task_context.sha256() == context_digest,
        {
            "expected": context_digest,
            "in_payload": semantic_payload.get("context_digest"),
            "recomputed": task_context.sha256(),
        },
    )
    # 23. INV-CTX-030: the packet carries the context body and its digest intact.
    check(
        "execution_packet_preserves_compiled_context",
        packet.get("compiled_task_context_digest") == context_digest
        and packet.get("compiled_task_context") == task_context.to_canonical_dict(),
        {"packet_digest": packet.get("compiled_task_context_digest")},
    )
    # 24. INV-CTX-024: every material context unknown reached an obligation.
    material = {
        unknown.unknown_id
        for unknown in task_context.unresolved_unknowns
        if unknown.materiality is UnknownMateriality.BLOCKING
    }
    conserved = {
        obligation.obligation_id.removeprefix("OBL.EPISTEMIC.CONTEXT.")
        for obligation in execution.obligations
        if obligation.obligation_id.startswith("OBL.EPISTEMIC.CONTEXT.")
    }
    check(
        "material_context_unknowns_are_conserved",
        material <= conserved,
        {"missing": sorted(material - conserved)},
    )

    if tuple(executed_checks) != _ALL_CHECKS:
        raise _fail(
            "liveness_check_coverage",
            {
                "expected": list(_ALL_CHECKS),
                "executed": list(executed_checks),
                "missing": [name for name in _ALL_CHECKS if name not in executed_checks],
            },
        )
    return LivenessReport(checks=tuple(executed_checks), passed=True)
