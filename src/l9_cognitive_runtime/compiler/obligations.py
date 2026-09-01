"""Obligation derivation and conservation (INV-003, A0304).

Obligations are stable, identifiably-typed semantic requirements derived once
from canonical intent (+ activation plan) and conserved through every
downstream IR — Activation, Execution, Graph, Validation, Handoff/Adapter —
until a legal terminal disposition is recorded. Disappearing, duplicating, or
silently renaming a required obligation is a compilation failure.
"""

from __future__ import annotations

from collections.abc import Iterable

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.models import (
    IntentContract,
    Obligation,
    ObligationDisposition,
    ObligationKind,
)
from l9_cognitive_runtime.models.context import CompiledTaskContext, UnknownMateriality
from l9_cognitive_runtime.models.errors import InvalidValueError

# Reserved owner names that always resolve (pipeline composition roots).
RESERVED_OWNERS = (
    "objective_deriver",
    "validation_runtime",
    "adapter_renderer",
    "context_compiler",
)

_TERMINAL_DISPOSITIONS = (
    ObligationDisposition.SATISFIED,
    ObligationDisposition.VALID_BLOCK,
    ObligationDisposition.SUPERSEDED_BY_HIGHER_AUTHORITY,
    ObligationDisposition.NOT_APPLICABLE_WITH_DETERMINISTIC_PROOF,
)


def _terminal_kernel(bindings: list[KernelBinding]) -> str:
    for binding in bindings:
        if binding.source_ref.endswith("flawless_victory.contract.yaml"):
            return binding.source_ref
    return "terminal:flawless_victory"


class ObligationDeriver:
    """Derive the canonical obligation set from intent, plan, and kernels."""

    def derive(
        self,
        intent: IntentContract,
        plan: ActivationPlan,
        kernels: list[KernelBinding],
        task_context: CompiledTaskContext,
    ) -> list[Obligation]:
        task_kernel = next(
            (
                binding.source_ref
                for binding in kernels
                if binding.source_ref.startswith("runtime/kernels/task/")
            ),
            "phase:P2_TASK_ROUTING",
        )
        source_ref = f"intent:{intent.intent_id}"
        obligations: list[Obligation] = [
            Obligation(
                obligation_id="OBL.AUTHORITY",
                kind=ObligationKind.AUTHORITY,
                source_ref=source_ref,
                required=True,
                owner="runtime/kernels/constitutional/K01-platform-architecture-engine.yaml",
                consumer_refs=["execution_contract"],
                evidence_requirements=["authority order respected with evidence"],
            ),
            # A0601: runtime-integrity validation is a distinct obligation from
            # objective validation — both bind to validation properties, but the
            # ladder belongs to runtime integrity alone.
            Obligation(
                obligation_id="OBL.RUNTIME_INTEGRITY",
                kind=ObligationKind.VALIDATION,
                source_ref=source_ref,
                required=True,
                owner="validation_runtime",
                consumer_refs=["validation_contract"],
                evidence_requirements=["command run or blocker reason"],
            ),
            Obligation(
                obligation_id="OBL.REALIZATION",
                kind=ObligationKind.REALIZATION,
                source_ref=source_ref,
                required=True,
                owner=task_kernel,
                consumer_refs=["execution_graph"],
                evidence_requirements=[
                    f"realization evidence for mode {intent.objective.realization_mode.value}"
                ],
            ),
        ]
        if intent.objective.validation_required:
            obligations.append(
                Obligation(
                    obligation_id="OBL.VALIDATION",
                    kind=ObligationKind.VALIDATION,
                    source_ref=source_ref,
                    required=True,
                    owner="validation_runtime",
                    consumer_refs=["validation_contract"],
                    evidence_requirements=["command run or blocker reason"],
                )
            )
        if intent.objective.delivery_required:
            obligations.append(
                Obligation(
                    obligation_id="OBL.DELIVERY",
                    kind=ObligationKind.DELIVERY,
                    source_ref=source_ref,
                    required=True,
                    owner=_terminal_kernel(kernels),
                    consumer_refs=["handoff_contract", "validation_contract"],
                    evidence_requirements=[
                        f"delivery evidence for mode {intent.objective.delivery_mode.value}"
                    ],
                )
            )
        # INV-008: every terminal success path crosses convergence; an
        # activated terminal phase derives the convergence obligation even
        # when pure outcome-accountability did not.
        if intent.accountability.required or plan.terminal_allowed:
            obligations.append(
                Obligation(
                    obligation_id="OBL.CONVERGENCE",
                    kind=ObligationKind.CONVERGENCE,
                    source_ref=source_ref,
                    required=True,
                    owner=_terminal_kernel(kernels),
                    consumer_refs=["validation_contract"],
                    evidence_requirements=["terminal disposition receipt"],
                )
            )
        materiality = plan.architecture_materiality or {}
        if materiality.get("required"):
            gar_kernel = next(
                (
                    binding.source_ref
                    for binding in kernels
                    if binding.source_ref.endswith("global_architect_kernel.yaml")
                ),
                "runtime/kernels/architecture/global_architect_kernel.yaml",
            )
            obligations.append(
                Obligation(
                    obligation_id="OBL.ARCHITECTURE",
                    kind=ObligationKind.ARCHITECTURE,
                    source_ref=source_ref,
                    required=True,
                    owner=gar_kernel,
                    consumer_refs=["validation_contract", "execution_graph"],
                    evidence_requirements=[
                        "architectural integrity evidence",
                        "plan readiness evidence",
                    ],
                )
            )
        if intent.objective.realization_mode.value == "UNKNOWN":
            obligations.append(
                Obligation(
                    obligation_id="OBL.EPISTEMIC.REALIZATION_RESOLUTION",
                    kind=ObligationKind.EPISTEMIC,
                    source_ref=source_ref,
                    required=True,
                    owner="objective_deriver",
                    consumer_refs=["handoff_contract"],
                    evidence_requirements=["deterministic realization resolution"],
                )
            )
        # INV-CTX-024: material (blocking) compiled-context unknowns are
        # conserved as required epistemic obligations, so they survive into
        # execution, handoff, validation, and the packet until legally disposed.
        # Non-blocking unknowns stay visible in the compiled context and in the
        # packet without creating an obligation — that is what non-material
        # means, and it is why an empty governed snapshot still compiles.
        for context_unknown in task_context.unresolved_unknowns:
            if context_unknown.materiality is not UnknownMateriality.BLOCKING:
                continue
            obligations.append(
                Obligation(
                    obligation_id=f"OBL.EPISTEMIC.CONTEXT.{context_unknown.unknown_id}",
                    kind=ObligationKind.EPISTEMIC,
                    source_ref=source_ref,
                    required=True,
                    owner="context_compiler",
                    consumer_refs=["handoff_contract"],
                    evidence_requirements=[
                        f"resolution or governed disposition of {context_unknown.reason_code.value}"
                    ],
                )
            )
        # Non-required epistemic notes for remaining unknowns: conserved but
        # never blocking.
        for index, unknown in enumerate(intent.unknowns or []):
            if unknown == "realization_mode_UNKNOWN":
                continue
            obligations.append(
                Obligation(
                    obligation_id=f"OBL.EPISTEMIC.UNKNOWN.{index}",
                    kind=ObligationKind.EPISTEMIC,
                    source_ref=source_ref,
                    required=False,
                    owner="objective_deriver",
                    consumer_refs=["handoff_contract"],
                    evidence_requirements=[f"resolution or disposition of: {unknown}"],
                )
            )
        return obligations


def _index(obligations: Iterable[Obligation]) -> dict[str, Obligation]:
    indexed: dict[str, Obligation] = {}
    for obligation in obligations:
        existing = indexed.get(obligation.obligation_id)
        if existing is not None:
            raise InvalidValueError(
                "duplicate obligation_id in one IR",
                path="obligations",
                details={"obligation_id": obligation.obligation_id},
            )
        indexed[obligation.obligation_id] = obligation
    return indexed


def _is_terminal(obligation: Obligation) -> bool:
    return obligation.disposition in _TERMINAL_DISPOSITIONS


def conserve(
    parent: list[Obligation],
    child: list[Obligation],
    *,
    stage: str,
) -> None:
    """Enforce INV-003 between a parent IR and a child IR (A0304).

    - duplicate_ids in either IR: fail.
    - missing_ids: every parent-required obligation without a legal terminal
      disposition must exist in the child with the same obligation_id.
    - silent_renaming: a conserved id must keep its kind.
    """
    parent_index = _index(parent)
    child_index = _index(child)
    for obligation_id, obligation in parent_index.items():
        if not obligation.required:
            continue
        if _is_terminal(obligation):
            continue
        child_obligation = child_index.get(obligation_id)
        if child_obligation is None:
            raise InvalidValueError(
                "required obligation disappeared between IRs",
                path=stage,
                details={
                    "obligation_id": obligation_id,
                    "parent": stage,
                    "child": f"{stage}+1",
                },
            )
        if child_obligation.kind is not obligation.kind:
            raise InvalidValueError(
                "obligation kind changed without a recorded disposition",
                path=stage,
                details={
                    "obligation_id": obligation_id,
                    "parent_kind": obligation.kind.value,
                    "child_kind": child_obligation.kind.value,
                },
            )


def conserve_ids(
    parent: list[Obligation],
    child_ids: list[str],
    *,
    stage: str,
) -> None:
    """INV-003 conservation where the child IR carries obligation ids only."""
    if len(child_ids) != len(set(child_ids)):
        raise InvalidValueError(
            "duplicate obligation_id in child IR",
            path=stage,
            details={"obligation_ids": child_ids},
        )
    parent_index = _index(parent)
    child_set = set(child_ids)
    for obligation_id, obligation in parent_index.items():
        if not obligation.required or _is_terminal(obligation):
            continue
        if obligation_id not in child_set:
            raise InvalidValueError(
                "required obligation disappeared between IRs",
                path=stage,
                details={"obligation_id": obligation_id},
            )
    for obligation_id in child_set:
        if obligation_id not in parent_index:
            raise InvalidValueError(
                "child IR references an obligation absent from the parent IR",
                path=stage,
                details={"obligation_id": obligation_id},
            )


def validate_obligations(
    obligations: list[Obligation],
    owner_registry: set[str],
    *,
    stage: str,
) -> None:
    """Structural obligations validation: owners resolve, consumers exist."""
    _index(obligations)  # duplicate check
    for obligation in obligations:
        if obligation.owner not in owner_registry:
            raise InvalidValueError(
                "obligation owner does not resolve",
                path=stage,
                details={"obligation_id": obligation.obligation_id, "owner": obligation.owner},
            )
        if obligation.required and not obligation.consumer_refs:
            raise InvalidValueError(
                "required obligation has no consumer",
                path=stage,
                details={"obligation_id": obligation.obligation_id},
            )


def owner_registry(plan: ActivationPlan, kernels: list[KernelBinding]) -> set[str]:
    """Build the resolvable-owner registry from the compiled activation."""
    registry = set(RESERVED_OWNERS)
    registry.update(f"phase:{phase_id}" for phase_id in plan.phase_sequence)
    registry.update(binding.source_ref for binding in kernels)
    registry.add("terminal:flawless_victory")
    return registry


def required_pending_ids(obligations: list[Obligation]) -> list[str]:
    """The obligation_ids that must propagate into the next IR."""
    return [
        obligation.obligation_id
        for obligation in obligations
        if obligation.required and not _is_terminal(obligation)
    ]
