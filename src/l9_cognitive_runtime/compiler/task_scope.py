"""Deterministic task-scope derivation (INV-CTX-006).

``TaskScopeCompiler`` turns the canonical ``IntentContract`` plus the caller's
*non-authoritative* ``source_context`` hints into a typed ``TaskScope``.

The distinction this module exists to hold: a caller hint may **narrow** what
the task is about (which files, which subsystem), but it may never **prove**
anything about the repository, the law, the authority, or the architecture.
Those only enter through a governed ``ContextSnapshot``.
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
# snapshot item.
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
    """Every reference a scoped context item may legally intersect."""
    return frozenset(scope.target_refs) | frozenset(scope.in_scope_refs)


__all__ = ["SCOPE_HINT_KEYS", "TaskScopeCompiler", "scope_reference_set"]
