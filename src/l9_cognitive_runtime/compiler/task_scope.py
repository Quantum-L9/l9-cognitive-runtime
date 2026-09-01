"""Deterministic task-scope derivation (INV-CTX-006).

``TaskScopeCompiler`` turns the canonical ``IntentContract`` plus the caller's
*non-authoritative* ``source_context`` hints into a typed ``TaskScope``.

The distinction this module exists to hold: a caller hint may **narrow** what
the task is about (which files, which subsystem), but it may never **prove**
anything about the repository, the law, the authority, or the architecture.
Those only enter through a governed ``ContextSnapshot``.

Exclusion is part of that narrowing and is real, not decorative. An excluded
reference leaves the eligible scope set entirely, so nothing scoped to it can
be selected. A reference named as both included and excluded is a genuine
contradiction: it becomes a blocking ``AMBIGUOUS_SCOPE`` unknown rather than
silently resolving to include.

Matching is exact. Path-prefix, glob, ancestry, and repository-hierarchy
semantics are deliberately *not* invented from plain strings: a typed selector
model would be needed to mean any of those, and guessing would quietly widen or
narrow scope in ways the caller never asked for.
"""

from __future__ import annotations

from typing import Any

from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.context import (
    ContextUnknown,
    TaskScope,
    UnknownMateriality,
    UnknownReasonCode,
)

# The only ``source_context`` keys that may narrow task scope. Every other key
# is inert: it cannot reach compiled semantics except as an explicit governed
# snapshot item. ``context_signals`` is deliberately absent (INV-CTX-014).
SCOPE_HINT_KEYS = ("target_refs", "in_scope_refs", "excluded_refs")


def _string_list(value: Any) -> list[str]:
    """Accept only a list of non-empty strings; anything else is not a hint."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


class TaskScopeCompiler:
    """Compile the typed task scope from intent plus normalized caller hints."""

    def compile(self, intent: IntentContract) -> TaskScope:
        hints = intent.source_context or {}
        target_refs = _string_list(hints.get("target_refs"))
        in_scope_refs = _string_list(hints.get("in_scope_refs"))
        excluded_refs = _string_list(hints.get("excluded_refs"))

        unknowns: list[ContextUnknown] = []

        # An exact reference that is both included and excluded is unresolvable
        # here: choosing include would silently defeat the exclusion, and
        # choosing exclude would silently drop a named target. It stays visible
        # and blocking, and the reference is absent from the eligible set either
        # way (INV-CTX-006).
        conflicting = sorted(set(target_refs) | set(in_scope_refs))
        conflicting = [ref for ref in conflicting if ref in set(excluded_refs)]
        if conflicting:
            unknowns.append(
                ContextUnknown(
                    reason_code=UnknownReasonCode.AMBIGUOUS_SCOPE,
                    materiality=UnknownMateriality.BLOCKING,
                    details={
                        "conflicting_refs": conflicting,
                        "reason": "reference is both included and excluded",
                    },
                )
            )

        if intent.objective.delivery_required and not (target_refs or in_scope_refs):
            # The mission asks for a change but names no subject. That is a real
            # scope ambiguity; it stays visible rather than being resolved into
            # a default. It is non-blocking because a legacy caller that never
            # supplied hints must still compile (INV-CTX-040).
            unknowns.append(
                ContextUnknown(
                    reason_code=UnknownReasonCode.AMBIGUOUS_SCOPE,
                    materiality=UnknownMateriality.NON_BLOCKING,
                    details={
                        "delivery_mode": intent.objective.delivery_mode.value,
                        "realization_mode": intent.objective.realization_mode.value,
                        "missing": "target_refs_and_in_scope_refs",
                    },
                )
            )

        return TaskScope(
            mission=intent.mission,
            task_type=intent.task_type,
            target_refs=target_refs,
            in_scope_refs=in_scope_refs,
            excluded_refs=excluded_refs,
            requested_outputs=list(intent.desired_outputs),
            constraints=list(intent.constraints),
            unresolved_unknowns=unknowns,
        )


def scope_reference_set(scope: TaskScope) -> frozenset[str]:
    """Every reference a scoped context item may legally intersect.

    Excluded references are removed, so no excluded reference can select scoped
    context (INV-CTX-006).
    """
    return scope.eligible_refs


__all__ = ["SCOPE_HINT_KEYS", "TaskScopeCompiler", "scope_reference_set"]
