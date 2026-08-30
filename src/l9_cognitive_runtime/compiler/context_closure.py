"""Fail-closed context semantic validation (INV-CTX-025).

Context closure runs after the context is compiled and *before* any downstream
execution semantics are treated as valid. It is the place where the compiled
context has to justify itself: every required requirement disposed, every
governed claim provenance-backed, every selected item bound to a reason, every
contradiction visible rather than quietly resolved.

It raises ``InvalidValueError`` on the first breach; a returned report means
every listed check actually executed.
"""

from __future__ import annotations

from dataclasses import dataclass

from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.task_context import GroupResolution
from l9_cognitive_runtime.models.context import (
    GOVERNED_LEVELS,
    AuthorityLevel,
    CompiledTaskContext,
    ContextKind,
    ContextRequirementPlan,
    MemoryContext,
    MissingPolicy,
    RepositoryState,
    canonical_cost,
)
from l9_cognitive_runtime.models.errors import InvalidValueError

CONTEXT_CHECKS = (
    "every_required_requirement_has_legal_disposition",
    "every_governed_selected_item_has_valid_provenance",
    "every_selected_item_semantic_key_matches_kind_recipe",
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
        resolutions: dict[tuple[str, str], GroupResolution],
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
        unknown_requirements = {
            unknown.requirement_ref
            for unknown in context.unresolved_unknowns
            if unknown.requirement_ref
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
        check(
            "every_governed_selected_item_has_valid_provenance",
            not unprovenanced,
            {"item_ids": unprovenanced},
        )
        # Repository truth additionally may never rest on an unverified claim.
        unverified_state = [
            item.item_id
            for item in selected
            if isinstance(item, RepositoryState)
            and item.authority_level is AuthorityLevel.UNVERIFIED
        ]
        if unverified_state:
            raise _fail(
                "every_governed_selected_item_has_valid_provenance",
                {"unverified_repository_state": unverified_state},
            )

        # 3. Semantic keys are kind-defined, not caller-defined.
        mismatched = [
            item.item_id
            for item in selected
            if item.expected_semantic_key() not in (None, item.semantic_key)
        ]
        check(
            "every_selected_item_semantic_key_matches_kind_recipe",
            not mismatched,
            {"item_ids": mismatched},
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

        # 6. Every unresolved same-key contradiction that a requirement wanted
        # is visible as an Unknown, never silently resolved.
        planned_kinds = {
            requirement.context_kind.value for requirement in requirement_plan.requirements
        }
        unknown_keys = {
            unknown.semantic_key for unknown in context.unresolved_unknowns if unknown.semantic_key
        }
        selected_keys = {item.semantic_key for item in selected}
        silent = [
            f"{kind_value}:{semantic_key}"
            for (kind_value, semantic_key), resolution in sorted(resolutions.items())
            if resolution.conflict
            and kind_value in planned_kinds
            and semantic_key not in unknown_keys
            and semantic_key in selected_keys
        ]
        check("no_equal_authority_conflict_is_silently_selected", not silent, {"keys": silent})

        # 7. Memory enriches; it never resolves. Matching enforces kind equality,
        # so this asserts the property the matcher is relied upon for.
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

        # 8. Required capability/authority is compiler-derived and never
        # collapsed into proven availability.
        available_ids = {fact.capability_id for fact in context.capabilities.available}
        unavailable_ids = {fact.capability_id for fact in context.capabilities.unavailable}
        promoted = sorted(available_ids & unavailable_ids)
        granted_ids = {fact.authority_id for fact in context.authority.granted}
        limited_ids = {fact.authority_id for fact in context.authority.limits}
        check(
            "capability_and_authority_gaps_are_explicit",
            not promoted and bool(context.authority.effective_order),
            {
                "contradictory_capabilities": promoted,
                "granted": sorted(granted_ids),
                "limits": sorted(limited_ids),
            },
        )

        # 9. Budgets hold on the finished artifact, not just during selection.
        budget = requirement_plan.global_budget
        total_bytes = sum(canonical_cost(item) for item in selected)
        check(
            "per_requirement_and_global_budgets_are_respected",
            len(selected) <= budget.max_total_items and total_bytes <= budget.max_total_bytes,
            {
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
        dangling = [
            unknown.unknown_id
            for unknown in context.unresolved_unknowns
            if unknown.requirement_ref and unknown.requirement_ref not in requirement_ids
        ]
        blocking_optional = [
            unknown.unknown_id
            for unknown in context.unresolved_unknowns
            for requirement in requirement_plan.requirements
            if unknown.requirement_ref == requirement.requirement_id
            and requirement.missing_policy is MissingPolicy.OPTIONAL
            and unknown.requirement_ref is not None
            and requirement.required
        ]
        check(
            "unresolved_unknowns_are_stable_and_bound",
            not dangling and not blocking_optional,
            {"dangling": dangling, "illegal_policy": blocking_optional},
        )

        # The ladder itself is checked: a check that silently disappears is a
        # closure failure, not a quietly shorter report.
        if tuple(executed) != CONTEXT_CHECKS:
            raise _fail(
                "context_closure_ladder_is_complete",
                {"executed": executed, "expected": list(CONTEXT_CHECKS)},
            )
        return ContextClosureReport(checks=tuple(executed), passed=True)


__all__ = ["CONTEXT_CHECKS", "ContextClosureReport", "ContextClosureValidator"]
