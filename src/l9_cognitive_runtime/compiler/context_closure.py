"""Fail-closed context semantic validation (INV-CTX-025).

Context closure runs after the context is compiled and *before* any downstream
execution semantics are treated as valid. It is the place where the compiled
context has to justify itself: every required requirement disposed, every
governed claim provenance-backed, every selected item bound to a reason, every
contradiction visible rather than quietly resolved.

The discipline that matters most here is that **a check must prove the property
it names**. Three of these are easy to write in a form that reads correct and
verifies almost nothing:

- a conflict check that only looks at keys which also happen to appear in the
  selected set never sees the conflict that disappeared entirely — which is the
  case worth catching;
- a budget check that verifies only the global budget passes a context where
  one requirement blew its own item or byte bound;
- a capability/authority check that verifies internal consistency proves
  nothing about whether each *required* capability or authority actually
  reached a disposition.

Each is therefore recomputed from the finished artifact.

It raises ``InvalidValueError`` on the first breach; a returned report means
every listed check actually executed.
"""

from __future__ import annotations

from dataclasses import dataclass

from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.task_context import (
    SnapshotResolution,
    authority_disposition,
    capability_disposition,
    matches_requirement,
)
from l9_cognitive_runtime.models.context import (
    GOVERNED_LEVELS,
    AuthorityLevel,
    CompiledTaskContext,
    ContextKind,
    ContextRequirement,
    ContextRequirementPlan,
    CoverageMode,
    MemoryContext,
    MissingPolicy,
    RepositoryState,
    UnknownReasonCode,
    canonical_cost,
)
from l9_cognitive_runtime.models.errors import InvalidValueError

CONTEXT_CHECKS = (
    "every_required_requirement_has_legal_disposition",
    "every_governed_selected_item_has_valid_provenance",
    "every_selected_item_identity_matches_kind_recipe",
    "every_selected_item_has_relevance_binding",
    "every_selected_kernel_equals_downstream_kernel_binding",
    "no_equal_authority_conflict_is_silently_selected",
    "no_memory_item_is_used_as_authoritative_resolution",
    "capability_and_authority_gaps_are_explicit",
    "per_requirement_and_global_budgets_are_respected",
    "unresolved_unknowns_are_stable_and_bound",
)


@dataclass(frozen=True)
class ContextClosureReport:
    checks: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {"checks": list(self.checks), "passed": self.passed}


def _fail(check: str, details: dict[str, object]) -> InvalidValueError:
    return InvalidValueError(
        f"context closure check failed: {check}", path="context_closure", details=details
    )


class ContextClosureValidator:
    """Validate that a compiled context is semantically closed."""

    def validate(
        self,
        *,
        context: CompiledTaskContext,
        requirement_plan: ContextRequirementPlan,
        resolution: SnapshotResolution,
        kernels: list[KernelBinding],
    ) -> ContextClosureReport:
        executed: list[str] = []

        def check(name: str, condition: bool, details: dict[str, object]) -> None:
            if not condition:
                raise _fail(name, details)
            executed.append(name)

        selected = context.selected_items()
        bound_requirements = {
            requirement_id for item in selected for requirement_id in item.selected_because
        }
        unknown_requirements: set[str] = {
            unknown.requirement_ref
            for unknown in context.unresolved_unknowns
            if unknown.requirement_ref is not None
        }

        # 1. Every required requirement is satisfied or legally disposed. An
        # OPTIONAL requirement needs neither.
        undisposed = [
            requirement.requirement_id
            for requirement in requirement_plan.requirements
            if requirement.required
            and requirement.requirement_id not in bound_requirements
            and requirement.requirement_id not in unknown_requirements
        ]
        check(
            "every_required_requirement_has_legal_disposition",
            not undisposed,
            {"requirement_ids": undisposed},
        )

        # 2. A governed claim without an immutable coordinate or content digest
        # is not governed truth.
        unprovenanced = [
            item.item_id
            for item in selected
            if item.authority_level in GOVERNED_LEVELS
            and not item.source_ref.has_immutable_provenance
        ]
        # Repository truth additionally may never rest on an unverified claim.
        unverified_state = [
            item.item_id
            for item in selected
            if isinstance(item, RepositoryState)
            and item.authority_level is AuthorityLevel.UNVERIFIED
        ]
        check(
            "every_governed_selected_item_has_valid_provenance",
            not unprovenanced and not unverified_state,
            {"item_ids": unprovenanced, "unverified_repository_state": unverified_state},
        )

        # 3. Semantic keys *and* item identity are kind-defined, not
        # caller-defined (INV-CTX-011). Recomputing identity here also catches a
        # claim field mutated after construction, which would otherwise leave a
        # stale identity behind.
        mismatched_keys = [
            item.item_id
            for item in selected
            if item.expected_semantic_key() not in (None, item.semantic_key)
        ]
        mismatched_ids = [
            item.item_id for item in selected if item.item_id != item.expected_item_id()
        ]
        check(
            "every_selected_item_identity_matches_kind_recipe",
            not mismatched_keys and not mismatched_ids,
            {"semantic_key_mismatch": mismatched_keys, "item_id_mismatch": mismatched_ids},
        )

        # 4. Nothing is in the context without a reason it is there.
        unbound = [item.item_id for item in selected if not item.selected_because]
        check("every_selected_item_has_relevance_binding", not unbound, {"item_ids": unbound})

        # 5. The context's kernels are the bindings downstream actually uses.
        check(
            "every_selected_kernel_equals_downstream_kernel_binding",
            context.selected_kernels == [binding.to_dict() for binding in kernels],
            {
                "context_kernels": [k.get("source_ref") for k in context.selected_kernels],
                "downstream_kernels": [binding.source_ref for binding in kernels],
            },
        )

        # 6. Every *eligible* unresolved same-key contradiction is visible as an
        # Unknown bound to the requirement that would have matched it. Restricting
        # this to keys that also appear selected would silently exempt the
        # conflict that vanished from the context entirely.
        disposed_pairs = {
            (unknown.requirement_ref, unknown.semantic_key)
            for unknown in context.unresolved_unknowns
            if unknown.reason_code is UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS
        }
        silent: list[str] = []
        for requirement in requirement_plan.requirements:
            for (kind_value, semantic_key), group in sorted(resolution.groups.items()):
                if not group.conflict or kind_value != requirement.context_kind.value:
                    continue
                if not any(matches_requirement(requirement, item) for item in group.sources):
                    continue
                if (requirement.requirement_id, semantic_key) not in disposed_pairs:
                    silent.append(f"{requirement.requirement_id}:{kind_value}:{semantic_key}")
        check("no_equal_authority_conflict_is_silently_selected", not silent, {"keys": silent})

        # 7. Memory enriches; it never resolves.
        memory_ids = {
            requirement.requirement_id
            for requirement in requirement_plan.requirements
            if requirement.context_kind is ContextKind.MEMORY_CONTEXT
        }
        leaked = [
            item.item_id
            for item in selected
            if isinstance(item, MemoryContext) and not set(item.selected_because) <= memory_ids
        ]
        governed_memory = [
            item.item_id
            for item in selected
            if isinstance(item, MemoryContext) and item.authority_level in GOVERNED_LEVELS
        ]
        check(
            "no_memory_item_is_used_as_authoritative_resolution",
            not leaked and not governed_memory,
            {"leaked": leaked, "governed_memory": governed_memory},
        )

        # 8. Every compiler-derived requirement reached exactly one explicit
        # disposition. Absence is a disposition; it is never a grant.
        capability_gaps = _undisposed_capabilities(context)
        authority_gaps = _undisposed_authorities(context)
        contradictory = sorted(
            {fact.capability_id for fact in context.capabilities.available}
            & {fact.capability_id for fact in context.capabilities.unavailable}
        )
        check(
            "capability_and_authority_gaps_are_explicit",
            not capability_gaps
            and not authority_gaps
            and not contradictory
            and bool(context.authority.effective_order),
            {
                "undisposed_capabilities": capability_gaps,
                "undisposed_authorities": authority_gaps,
                "contradictory_capabilities": contradictory,
            },
        )

        # 9. Budgets hold on the finished artifact — per requirement *and*
        # globally. A per-requirement breach that fits inside the global budget
        # is exactly what a global-only check misses.
        breaches = _budget_breaches(context, requirement_plan, unknown_requirements)
        budget = requirement_plan.global_budget
        total_bytes = sum(canonical_cost(item) for item in selected)
        global_ok = (
            len(selected) <= budget.max_total_items and total_bytes <= budget.max_total_bytes
        )
        check(
            "per_requirement_and_global_budgets_are_respected",
            not breaches and global_ok,
            {
                "per_requirement": breaches,
                "items": len(selected),
                "max_total_items": budget.max_total_items,
                "bytes": total_bytes,
                "max_total_bytes": budget.max_total_bytes,
            },
        )

        # 10. Unknown identity is deterministic and every bound reference
        # resolves to a planned requirement.
        requirement_ids = {
            requirement.requirement_id for requirement in requirement_plan.requirements
        }
        by_id = {
            requirement.requirement_id: requirement for requirement in requirement_plan.requirements
        }
        dangling = [
            unknown.unknown_id
            for unknown in context.unresolved_unknowns
            if unknown.requirement_ref and unknown.requirement_ref not in requirement_ids
        ]
        unstable = [
            unknown.unknown_id
            for unknown in context.unresolved_unknowns
            if unknown.unknown_id != unknown.expected_unknown_id()
        ]
        illegal_policy = [
            unknown.unknown_id
            for unknown in context.unresolved_unknowns
            if unknown.requirement_ref in by_id
            and by_id[str(unknown.requirement_ref)].missing_policy is MissingPolicy.OPTIONAL
            and by_id[str(unknown.requirement_ref)].required
        ]
        check(
            "unresolved_unknowns_are_stable_and_bound",
            not dangling and not unstable and not illegal_policy,
            {"dangling": dangling, "unstable": unstable, "illegal_policy": illegal_policy},
        )

        # The ladder itself is checked: a check that silently disappears is a
        # closure failure, not a quietly shorter report.
        if tuple(executed) != CONTEXT_CHECKS:
            raise _fail(
                "context_closure_ladder_is_complete",
                {"executed": executed, "expected": list(CONTEXT_CHECKS)},
            )
        return ContextClosureReport(checks=tuple(executed), passed=True)


def _undisposed_capabilities(context: CompiledTaskContext) -> list[str]:
    """Required capabilities whose disposition is not explicitly recorded."""
    available = {fact.capability_id for fact in context.capabilities.available}
    unavailable = {fact.capability_id for fact in context.capabilities.unavailable}
    unknown_facts = {fact.capability_id for fact in context.capabilities.unknown}
    recorded = {
        str(unknown.details.get("capability_id"))
        for unknown in context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.UNSUPPORTED_CAPABILITY
    }
    gaps: list[str] = []
    for requirement in context.capabilities.required:
        state = capability_disposition(
            requirement.capability_id, available, unavailable, unknown_facts
        )
        if state == "available":
            continue
        if requirement.capability_id not in recorded:
            gaps.append(requirement.capability_id)
    return sorted(gaps)


def _undisposed_authorities(context: CompiledTaskContext) -> list[str]:
    """Required authorities whose disposition is not explicitly recorded.

    The compiler default order never appears here: precedence is not permission
    (INV-CTX-022), so a required authority is satisfied only by a proven grant.
    """
    granted = {fact.authority_id for fact in context.authority.granted}
    limits = {fact.authority_id for fact in context.authority.limits}
    unknown_facts = {fact.authority_id for fact in context.authority.unknown}
    recorded = {
        str(unknown.details.get("authority_id"))
        for unknown in context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.MISSING_AUTHORITY
    }
    gaps: list[str] = []
    for requirement in context.authority.required:
        state = authority_disposition(requirement.authority_id, granted, limits, unknown_facts)
        if state == "granted":
            continue
        if requirement.authority_id not in recorded:
            gaps.append(requirement.authority_id)
    return sorted(gaps)


def _budget_breaches(
    context: CompiledTaskContext,
    requirement_plan: ContextRequirementPlan,
    disposed_requirements: set[str],
) -> list[dict[str, object]]:
    """Recompute each requirement's own footprint from the finished context."""
    selected = context.selected_items()
    breaches: list[dict[str, object]] = []
    conflict_keys: dict[str, set[str]] = {}
    for unknown in context.unresolved_unknowns:
        if (
            unknown.reason_code is UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS
            and unknown.requirement_ref
            and unknown.semantic_key
        ):
            conflict_keys.setdefault(unknown.requirement_ref, set()).add(unknown.semantic_key)

    for requirement in requirement_plan.requirements:
        items = [item for item in selected if requirement.requirement_id in item.selected_because]
        count = len(items)
        cost = sum(canonical_cost(item) for item in items)
        breach = _requirement_breach(
            requirement,
            count=count,
            cost=cost,
            keys={item.semantic_key for item in items},
            disposed_keys=conflict_keys.get(requirement.requirement_id, set()),
            was_disposed=requirement.requirement_id in disposed_requirements,
        )
        if breach is not None:
            breaches.append(breach)
    return breaches


def _requirement_breach(
    requirement: ContextRequirement,
    *,
    count: int,
    cost: int,
    keys: set[str],
    disposed_keys: set[str],
    was_disposed: bool,
) -> dict[str, object] | None:
    if requirement.max_items is not None and count > requirement.max_items:
        return {
            "requirement_id": requirement.requirement_id,
            "breach": "max_items",
            "selected": count,
            "max_items": requirement.max_items,
        }
    if requirement.max_bytes is not None and cost > requirement.max_bytes:
        return {
            "requirement_id": requirement.requirement_id,
            "breach": "max_bytes",
            "bytes": cost,
            "max_bytes": requirement.max_bytes,
        }
    if was_disposed:
        # An explicitly disposed requirement is allowed to be under-covered;
        # that disposition is what check 1 verified.
        return None
    if not requirement.required:
        # ``min_items`` on an optional requirement is a target, not a floor: its
        # OPTIONAL missing policy is precisely the statement that taking nothing
        # is legal. Ceilings above still apply to it — a ceiling is a ceiling.
        return None
    if count < requirement.min_items:
        return {
            "requirement_id": requirement.requirement_id,
            "breach": "min_items",
            "selected": count,
            "min_items": requirement.min_items,
        }
    if requirement.coverage_mode is CoverageMode.SEMANTIC_KEYS:
        missing = sorted(set(requirement.required_semantic_keys) - keys - disposed_keys)
        if missing:
            return {
                "requirement_id": requirement.requirement_id,
                "breach": "required_semantic_keys",
                "missing": missing,
            }
    return None


__all__ = ["CONTEXT_CHECKS", "ContextClosureReport", "ContextClosureValidator"]
