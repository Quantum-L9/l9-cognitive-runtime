"""Canonical objective derivation (INV-002): exactly one owner of intent facts.

``ObjectiveDeriver`` turns a ``CompileRequest`` into the canonical typed
``IntentContract`` — including the objective specification (realization mode,
validation requirement, delivery requirement/mode) and the accountability
requirement — before any policy, routing, or kernel selection runs. Nothing
downstream may re-derive these facts; kernels and compilers consume the typed
intent.
"""

from __future__ import annotations

import re

from l9_cognitive_runtime.models import (
    DeliveryMode,
    IntentContract,
    RealizationMode,
)
from l9_cognitive_runtime.types import CompileRequest

# Word-boundary verb families. Mixed analysis+mutation intent deterministically
# retains MUTATION (A0201): an audit-and-fix mission is a mutation mission.
_MUTATION_VERBS = (
    "add",
    "adjust",
    "build",
    "change",
    "convert",
    "create",
    "delete",
    "extend",
    "fix",
    "harden",
    "implement",
    "install",
    "migrate",
    "modify",
    "optimize",
    "refactor",
    "remove",
    "repair",
    "replace",
    "rewrite",
    "update",
    "upgrade",
    "write",
)

_ANALYSIS_VERBS = (
    "analyse",
    "analyze",
    "assess",
    "audit",
    "check",
    "evaluate",
    "examine",
    "explore",
    "inspect",
    "investigate",
    "review",
    "understand",
)

_ARTIFACT_VERBS = (
    "document",
    "draft",
    "generate",
    "produce",
    "spec",
)

_DECISION_VERBS = (
    "choose",
    "decide",
    "prioritize",
    "recommend",
    "select",
)


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def derive_realization_mode(mission: str) -> RealizationMode:
    """Deterministic realization derivation from explicit mission text."""
    lowered = mission.lower()
    mutation = _has_word(lowered, _MUTATION_VERBS)
    analysis = _has_word(lowered, _ANALYSIS_VERBS)
    if mutation:
        # A0201: analyze-and-fix / audit-and-repair mixed intent retains MUTATION.
        return RealizationMode.MUTATION
    if analysis:
        return RealizationMode.ANALYSIS
    if _has_word(lowered, _ARTIFACT_VERBS):
        return RealizationMode.ARTIFACT
    if _has_word(lowered, _DECISION_VERBS):
        return RealizationMode.DECISION
    return RealizationMode.UNKNOWN


class ObjectiveDeriver:
    """Derive the canonical intent contract from an explicit compile request."""

    def derive(self, request: CompileRequest) -> IntentContract:
        mission = request.mission
        realization = derive_realization_mode(mission)
        unknowns = list(request.unknowns)
        if realization is RealizationMode.UNKNOWN:
            # A0203: UNKNOWN realization stays visible and blocking; it must
            # not be silently resolved into a default execution shape.
            unknowns.append("realization_mode_UNKNOWN")

        mutation_delivery = realization is RealizationMode.MUTATION
        artifact_delivery = realization is RealizationMode.ARTIFACT
        delivery_required = mutation_delivery or artifact_delivery
        if realization is RealizationMode.MUTATION:
            delivery_mode = DeliveryMode.IN_PLACE_WORKSPACE
        elif realization is RealizationMode.ARTIFACT:
            delivery_mode = DeliveryMode.RETURNED_FILES
        else:
            delivery_mode = DeliveryMode.NONE

        # Unknown realization must be validated before it can proceed; mutation
        # and artifact missions are validated by construction.
        validation_required = realization in {
            RealizationMode.MUTATION,
            RealizationMode.ARTIFACT,
            RealizationMode.UNKNOWN,
        }
        accountability_required = validation_required or delivery_required

        return IntentContract.from_mapping(
            {
                "intent_id": "intent.runtime_convergence.v1",
                "mission": mission,
                "task_type": request.task_type,
                "constraints": list(request.constraints),
                "desired_outputs": list(request.desired_outputs),
                "source_context": dict(request.source_context),
                "unknowns": unknowns,
                "objective": {
                    "requested": True,
                    "realization_mode": realization.value,
                    "acceptance_conditions": [],
                    "validation_required": validation_required,
                    "delivery_required": delivery_required,
                    "delivery_mode": delivery_mode.value,
                },
                "accountability": {"required": accountability_required},
            }
        )
