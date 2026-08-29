"""INV-013 / A0702: the adapter-weakening liveness check must be real.

`no_adapter_drops_blocking_obligation` was declared in `_ALL_CHECKS` and
appended to the executed-check list without evaluating anything, and
`validate_packet` ran only when an adapter was rendered — never on the
fresh-compile spine. A packet that drops a blocking obligation therefore
reached callers unchallenged, and the liveness report named a check that had
not run (a false-completion signal the contract forbids).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.compiler import pipeline as pipeline_module
from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.liveness import (
    _ALL_CHECKS,
    LivenessReport,
    validate_runtime_semantic_liveness,
)
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle

MISSION = "Add safe retry behavior to this asynchronous payment worker."
SIGNALS = {
    "pack": "test",
    "context_signals": [
        "message_redelivery_possible",
        "external_side_effect",
        "multiple_workers",
    ],
}


def _request(pack: Path) -> CompileRequest:
    return CompileRequest(mission=MISSION, pack_root=pack, source_context=dict(SIGNALS))


def _run_liveness(
    bundle: RuntimeBundle, pack: Path, packet: dict[str, Any]
) -> LivenessReport:
    plan = ActivationPlanner().plan(
        ObjectiveDeriver().derive(
            CompileRequest(mission=MISSION, pack_root=pack, source_context=dict(SIGNALS))
        ),
        rules_path=pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
    )
    return validate_runtime_semantic_liveness(
        intent=bundle.intent,
        plan=plan,
        kernels=KernelResolver().resolve(list(bundle.execution.kernel_activation), pack),
        execution=bundle.execution,
        validation=bundle.validation,
        handoff=bundle.handoff,
        graph=bundle.graph,
        packet=packet,
    )


def test_liveness_detects_packet_dropping_blocking_obligation(valid_pack: Path) -> None:
    """A packet missing a required blocking obligation must fail closed."""
    bundle = CognitiveRuntimeService().compile_runtime(_request(valid_pack))
    weakened = copy.deepcopy(bundle.packet)
    dropped = weakened["required_obligations"].pop()
    assert dropped["obligation_id"]
    with pytest.raises(InvalidValueError, match="no_adapter_drops_blocking_obligation"):
        _run_liveness(bundle, valid_pack, weakened)


def test_liveness_accepts_the_live_packet(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(_request(valid_pack))
    report = _run_liveness(bundle, valid_pack, bundle.packet)
    assert report.passed


def test_liveness_executes_every_declared_check(valid_pack: Path) -> None:
    """Coverage is enforced: a declared check may never silently not run."""
    bundle = CognitiveRuntimeService().compile_runtime(_request(valid_pack))
    report = _run_liveness(bundle, valid_pack, bundle.packet)
    assert report.checks == _ALL_CHECKS


def test_compile_spine_validates_the_execution_packet(
    valid_pack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`validate_packet` must run on every fresh compile, not only on render."""
    seen: list[dict[str, object]] = []

    def _spy(packet: dict[str, object]) -> None:
        seen.append(packet)

    monkeypatch.setattr(pipeline_module, "validate_packet", _spy)
    CognitiveRuntimeService().compile_runtime(_request(valid_pack))
    assert seen, "validate_packet was never called on the compile path"
