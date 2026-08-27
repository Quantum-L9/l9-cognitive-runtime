"""Canonical objective derivation (INV-002): exactly one owner of intent facts.

``ObjectiveDeriver`` turns a ``CompileRequest`` into the canonical typed
``IntentContract`` before any policy, routing, or kernel selection runs.
Nothing downstream may re-derive these facts; kernels and compilers consume
the typed intent.
"""

from __future__ import annotations

from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.types import CompileRequest


class ObjectiveDeriver:
    """Derive the canonical intent contract from an explicit compile request."""

    def derive(self, request: CompileRequest) -> IntentContract:
        return IntentContract.from_mapping(
            {
                "intent_id": "intent.runtime_convergence.v1",
                "mission": request.mission,
                "task_type": request.task_type,
                "constraints": list(request.constraints),
                "desired_outputs": list(request.desired_outputs),
                "source_context": dict(request.source_context),
                "unknowns": list(request.unknowns),
            }
        )
