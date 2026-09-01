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
  reached a disposition;
- a budget check that verifies ceilings and ``min_items`` proves nothing about
  ``all_eligible`` coverage: a selection bug that silently drops one eligible
  item while leaving enough behind to clear ``min_items`` passes it. Coverage
  modes are therefore proven against an independently recomputed eligible set,
  not against the count the selector happened to reach. A bare
  ``BUDGET_INSUFFICIENT`` receipt is not a waiver either: under-coverage is
  legal only when a deterministic witness proves the next eligible candidate
  would actually violate the recorded bound.

Each is therefore recomputed from the finished artifact.

It raises ``InvalidValueError`` on the first breach; a returned report means
every listed check actually executed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.task_context import (
    ResolvedCandidates,
    SnapshotResolution,
    _candidate_sort_key,
    authority_disposition,
    capability_disposition,
    matches_requirement,
)
from l9_cognitive_runtime.models.context import (
    GOVERNED_LEVELS,
    AuthorityLevel,
    CompiledTaskContext,
    ContextItemIdentity,
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
    "every_coverage_mode_is_independently_proven",
    "unresolved_unknowns_are_stable_and_bound",
)


# Reason codes that actually *dispose* of a requirement's coverage. An advisory
# unknown that merely happens to be bound to a requirement — a dangling
# supersession reference, say — is not a licence to leave it uncovered.
DISPOSING_REASON_CODES = frozenset(
    {
        UnknownReasonCode.MISSING_REQUIRED_CONTEXT,
        UnknownReasonCode.BUDGET_INSUFFICIENT,
        UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS,
    }
)


@dataclass(frozen=True)
class ContextClosureReport:
    checks: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {"checks": list(self.checks), "passed": self.passed}


def _eligibility_of(
    requirement: ContextRequirement,
) -> Callable[[ContextItemIdentity], bool]:
    """Bind the compiler's own matching rule to one requirement."""

    def eligible(item: ContextItemIdentity) -> bool:
        return matches_requirement(requirement, item)

    return eligible


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
            if unknown.requirement_ref is not None and unknown.reason_code in DISPOSING_REASON_CODES
        }

        # Independently recomputed per-requirement eligible views. Closure never
        # trusts a resolution someone else already reduced: it re-runs the
        # compiler's own eligibility rule over the candidates and resolves each
        # requirement's set itself, which is what makes the coverage proofs
        # below evidence rather than restatement.
        views: dict[str, ResolvedCandidates] = {
            requirement.requirement_id: resolution.resolve(_eligibility_of(requirement))
            for requirement in requirement_plan.requirements
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
            for (kind_value, semantic_key), group in sorted(
                views[requirement.requirement_id].groups.items()
            ):
                if not group.conflict:
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

        # 10. Each coverage mode means what it says, proven against the eligible
        # set recomputed here rather than against the count the selector
        # reached. `all_eligible` that quietly dropped one item while still
        # clearing `min_items` is exactly what check 9 cannot see.
        coverage = _coverage_breaches(context, requirement_plan, views)
        check(
            "every_coverage_mode_is_independently_proven",
            not coverage,
            {"breaches": coverage},
        )

        # 11. Unknown identity is deterministic and every bound reference
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
    recorded = {
        str(unknown.semantic_key)
        for unknown in context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.MISSING_AUTHORITY
    }
    gaps: list[str] = []
    for requirement in context.authority.required:
        state = authority_disposition(
            requirement,
            context.authority.granted,
            context.authority.limits,
            context.authority.unknown,
        )
        if state == "granted":
            continue
        # Keyed by the requirement's full semantic key, so a gap over one
        # subject or action scope is not closed by a record about another.
        if requirement.semantic_key not in recorded:
            gaps.append(requirement.semantic_key)
    return sorted(gaps)


def _eligible_items(view: ResolvedCandidates) -> dict[str, str]:
    """Item identity -> semantic key for what a requirement could select.

    Conflicting groups are excluded: an unresolvable contradiction is disposed,
    never selected, so it is not material the selector failed to take.
    """
    return {
        item.item_id: item.semantic_key
        for group in view.groups.values()
        if not group.conflict
        for item in group.items
    }


def _conflict_disposed_keys(context: CompiledTaskContext) -> dict[str, set[str]]:
    """Semantic keys each requirement disposed as an unresolvable conflict."""
    keys: dict[str, set[str]] = {}
    for unknown in context.unresolved_unknowns:
        if (
            unknown.reason_code is UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS
            and unknown.requirement_ref
            and unknown.semantic_key
        ):
            keys.setdefault(unknown.requirement_ref, set()).add(unknown.semantic_key)
    return keys


_BUDGET_WITNESS_KEYS = (
    "bound",
    "blocked_item_id",
    "observed_count",
    "observed_bytes",
    "candidate_cost",
    "limit",
)


def _eligible_frontier(
    requirement: ContextRequirement,
    view: ResolvedCandidates,
) -> list[ContextItemIdentity]:
    """The deterministic candidates the selector was entitled to consider."""
    items = [item for group in view.groups.values() if not group.conflict for item in group.items]
    items.sort(key=_candidate_sort_key)
    frontier: list[ContextItemIdentity] = []
    for item in items:
        if (
            requirement.coverage_mode is CoverageMode.MINIMUM
            and len(frontier) >= requirement.min_items
        ):
            break
        if (
            requirement.coverage_mode is CoverageMode.SEMANTIC_KEYS
            and item.semantic_key not in requirement.required_semantic_keys
        ):
            continue
        frontier.append(item)
    return frontier


def _budget_witness(unknown: Any) -> dict[str, Any] | None:
    details = unknown.details
    if not all(key in details for key in _BUDGET_WITNESS_KEYS):
        return None
    return {key: details[key] for key in _BUDGET_WITNESS_KEYS}


def _budget_stop_independently_proven(
    context: CompiledTaskContext,
    requirement: ContextRequirement,
    view: ResolvedCandidates,
    requirement_plan: ContextRequirementPlan,
) -> bool:
    """True only when a budget-stop witness independently verifies.

    A bare ``BUDGET_INSUFFICIENT`` reason code is not a waiver. Closure
    recomputes the eligible frontier and proves that admitting the blocked
    next candidate would violate the recorded bound (INV-CTX-025/026).
    """
    unknown = next(
        (
            item
            for item in context.unresolved_unknowns
            if item.reason_code is UnknownReasonCode.BUDGET_INSUFFICIENT
            and item.requirement_ref == requirement.requirement_id
        ),
        None,
    )
    if unknown is None:
        return False
    witness = _budget_witness(unknown)
    if witness is None:
        return False
    taken_ids = {
        item.item_id
        for item in context.selected_items()
        if requirement.requirement_id in item.selected_because
    }
    frontier = _eligible_frontier(requirement, view)
    admitted = [item for item in frontier if item.item_id in taken_ids]
    blocked = next((item for item in frontier if item.item_id not in taken_ids), None)
    if blocked is None or blocked.item_id != witness["blocked_item_id"]:
        return False
    if canonical_cost(blocked) != witness["candidate_cost"]:
        return False
    bound = witness["bound"]
    if bound == "requirement_max_items":
        return (
            requirement.max_items is not None
            and witness["limit"] == requirement.max_items
            and witness["observed_count"] == len(admitted)
            and len(admitted) + 1 > requirement.max_items
        )
    if bound == "requirement_max_bytes":
        observed = sum(canonical_cost(item) for item in admitted)
        return (
            requirement.max_bytes is not None
            and witness["limit"] == requirement.max_bytes
            and witness["observed_bytes"] == observed
            and observed + canonical_cost(blocked) > requirement.max_bytes
        )
    unique = {item.item_id: item for item in context.selected_items()}
    if blocked.item_id in unique:
        return False
    budget = requirement_plan.global_budget
    if bound == "global_max_items":
        return (
            witness["limit"] == budget.max_total_items
            and witness["observed_count"] == len(unique)
            and len(unique) + 1 > budget.max_total_items
        )
    if bound == "global_max_bytes":
        observed = sum(canonical_cost(item) for item in unique.values())
        return (
            witness["limit"] == budget.max_total_bytes
            and witness["observed_bytes"] == observed
            and observed + canonical_cost(blocked) > budget.max_total_bytes
        )
    return False


def _coverage_breaches(
    context: CompiledTaskContext,
    requirement_plan: ContextRequirementPlan,
    views: dict[str, ResolvedCandidates],
) -> list[dict[str, object]]:
    """Prove every requirement's coverage mode against its own eligible set."""
    selected = context.selected_items()
    disposed = _conflict_disposed_keys(context)
    breaches: list[dict[str, object]] = []
    for requirement in requirement_plan.requirements:
        taken = [item for item in selected if requirement.requirement_id in item.selected_because]
        view = views[requirement.requirement_id]
        breach = _coverage_breach(
            requirement,
            eligible=_eligible_items(view),
            taken={item.item_id for item in taken},
            taken_keys={item.semantic_key for item in taken},
            disposed_keys=disposed.get(requirement.requirement_id, set()),
            truncated=_budget_stop_independently_proven(
                context, requirement, view, requirement_plan
            ),
        )
        if breach is not None:
            breaches.append(breach)
    return breaches


def _coverage_breach(
    requirement: ContextRequirement,
    *,
    eligible: dict[str, str],
    taken: set[str],
    taken_keys: set[str],
    disposed_keys: set[str],
    truncated: bool,
) -> dict[str, object] | None:
    """One requirement's coverage mode, judged against its own eligible set.

    Under-coverage is legal only when a budget stop was **independently
    proven** for this requirement. A missing policy of ``OPTIONAL`` is deliberately not a waiver
    here: OPTIONAL governs *absence* — that taking nothing is legal when
    nothing was eligible — and says nothing about selector correctness.
    Eligible material the selector knew about and did not take is a defect
    whatever the policy says about absence, and treating OPTIONAL as a waiver
    would exempt from proof exactly the requirements most of the plan uses.

    Over-coverage — selecting what was never eligible, or more than the mode
    asks for — is never legal, budget stop or not.
    """
    ineligible = sorted(taken - set(eligible))
    if ineligible:
        return {
            "requirement_id": requirement.requirement_id,
            "breach": "ineligible_selection",
            "item_ids": ineligible,
        }
    if requirement.coverage_mode is CoverageMode.ALL_ELIGIBLE:
        missed = sorted(set(eligible) - taken)
        if missed and not truncated:
            return {
                "requirement_id": requirement.requirement_id,
                "breach": "all_eligible_incomplete",
                "unselected_eligible": missed,
            }
        return None
    if requirement.coverage_mode is CoverageMode.MINIMUM:
        # `minimum` means the minimum, not "at least min_items": taking more
        # than the mode asks for is unbounded context growth by another name.
        expected = min(requirement.min_items, len(eligible))
        if len(taken) > expected:
            return {
                "requirement_id": requirement.requirement_id,
                "breach": "minimum_exceeded",
                "selected": len(taken),
                "expected": expected,
            }
        if len(taken) < expected and not truncated:
            return {
                "requirement_id": requirement.requirement_id,
                "breach": "minimum_incomplete",
                "selected": len(taken),
                "expected": expected,
            }
        return None
    required_keys = set(requirement.required_semantic_keys)
    unrequested = sorted(taken_keys - required_keys)
    if unrequested:
        return {
            "requirement_id": requirement.requirement_id,
            "breach": "semantic_keys_exceeded",
            "unrequested_keys": unrequested,
        }
    # Only keys that actually had an eligible candidate. A required key with no
    # candidate at all is absence, which the missing policy governs and check 9
    # judges; this check is about candidates the selector saw and skipped.
    reachable = set(eligible.values()) & required_keys
    unselected = sorted(reachable - taken_keys - disposed_keys)
    if unselected and not truncated:
        return {
            "requirement_id": requirement.requirement_id,
            "breach": "semantic_keys_incomplete",
            "unselected_required_keys": unselected,
        }
    return None


def _budget_breaches(
    context: CompiledTaskContext,
    requirement_plan: ContextRequirementPlan,
    disposed_requirements: set[str],
) -> list[dict[str, object]]:
    """Recompute each requirement's own footprint from the finished context."""
    selected = context.selected_items()
    breaches: list[dict[str, object]] = []
    conflict_keys = _conflict_disposed_keys(context)

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


__all__ = [
    "CONTEXT_CHECKS",
    "DISPOSING_REASON_CODES",
    "ContextClosureReport",
    "ContextClosureValidator",
]
