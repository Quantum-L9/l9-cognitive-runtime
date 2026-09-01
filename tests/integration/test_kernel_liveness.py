"""LIVE-005: activating GAR without a downstream consumer fails liveness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.context_closure import CONTEXT_CHECKS, ContextClosureReport
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.liveness import _ALL_CHECKS, validate_runtime_semantic_liveness
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.models.context import ContextSnapshot
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle
from tests.conftest import discovery_for, governed_signal_snapshot

MISSION = "Add safe retry behavior to this asynchronous payment worker."

# INV-CTX-014: the same signals, now proven as governed constraints rather than
# asserted as raw caller hints.
GOVERNED_SIGNALS = (
    "message_redelivery_possible",
    "external_side_effect",
    "multiple_workers",
)


def _snapshot() -> ContextSnapshot:
    return governed_signal_snapshot(*GOVERNED_SIGNALS)


def _gar_mission_request(pack: Path) -> CompileRequest:
    return CompileRequest(mission=MISSION, pack_root=pack, source_context={"pack": "test"})


def _liveness_kwargs(bundle: RuntimeBundle, pack: Path) -> dict[str, Any]:
    """Rebuild the liveness inputs for a compiled bundle.

    The closure report is supplied as a passing fixture: the closure ladder has
    its own suite, and what these tests exercise is the liveness ladder over an
    edited bundle.
    """
    intent = ObjectiveDeriver().derive(_gar_mission_request(pack))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
        discovery=discovery_for(intent, _snapshot()),
    )
    context_digest = bundle.digests()["context"]
    return {
        "intent": bundle.intent,
        "plan": plan,
        "kernels": KernelResolver().resolve(list(bundle.execution.kernel_activation), pack),
        "execution": bundle.execution,
        "validation": bundle.validation,
        "handoff": bundle.handoff,
        "graph": bundle.graph,
        "task_context": bundle.task_context,
        "context_digest": context_digest,
        "closure_report": ContextClosureReport(checks=CONTEXT_CHECKS, passed=True),
        "packet": bundle.packet,
        "semantic_payload": {"context_digest": context_digest},
    }


def test_live005_gar_without_validation_consumer_fails_liveness(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        _gar_mission_request(valid_pack), context_snapshot=_snapshot()
    )
    # Strip the architecture validation properties — GAR activates but its
    # downstream consumer is gone.
    stripped = [
        p for p in bundle.validation.validation_properties if p.obligation_ref != "OBL.ARCHITECTURE"
    ]
    bundle.validation.validation_properties = stripped
    with pytest.raises(
        InvalidValueError, match="every_required_validation_obligation_has_evidence_path"
    ):
        validate_runtime_semantic_liveness(**_liveness_kwargs(bundle, valid_pack))


def test_live005_full_liveness_passes_for_live_bundle(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        _gar_mission_request(valid_pack), context_snapshot=_snapshot()
    )
    report = validate_runtime_semantic_liveness(**_liveness_kwargs(bundle, valid_pack))
    assert report.passed is True
    # Coverage is the assertion, not a hand-maintained count: every declared
    # check must have executed, in order.
    assert report.checks == _ALL_CHECKS
