"""LIVE-005: activating GAR without a downstream consumer fails liveness."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.liveness import (
    _ALL_CHECKS,
    validate_runtime_semantic_liveness,
)
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import CompileRequest as Request


def _gar_mission_request(pack: Path) -> CompileRequest:
    return CompileRequest(
        mission="Add safe retry behavior to this asynchronous payment worker.",
        pack_root=pack,
        source_context={
            "pack": "test",
            "context_signals": [
                "message_redelivery_possible",
                "external_side_effect",
                "multiple_workers",
            ],
        },
    )


def test_live005_gar_without_validation_consumer_fails_liveness(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(_gar_mission_request(valid_pack))
    # Strip the architecture validation properties — GAR activates but its
    # downstream consumer is gone.
    stripped = [
        p for p in bundle.validation.validation_properties if p.obligation_ref != "OBL.ARCHITECTURE"
    ]
    bundle.validation.validation_properties = stripped
    with pytest.raises(
        InvalidValueError, match="every_required_validation_obligation_has_evidence_path"
    ):
        validate_runtime_semantic_liveness(
            intent=bundle.intent,
            plan=ActivationPlanner().plan(
                ObjectiveDeriver().derive(
                    Request(mission="Add safe retry behavior to this asynchronous payment worker.")
                ),
                rules_path=(
                    valid_pack
                    / "runtime"
                    / "kernel_pipeline"
                    / "planner"
                    / "TASK_ROUTING_RULES.yaml"
                ),
                pipeline_path=(valid_pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml"),
            ),
            kernels=KernelResolver().resolve(list(bundle.execution.kernel_activation), valid_pack),
            execution=bundle.execution,
            validation=bundle.validation,
            handoff=bundle.handoff,
            graph=bundle.graph,
        )


def test_live005_full_liveness_passes_for_live_bundle(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(_gar_mission_request(valid_pack))
    report = validate_runtime_semantic_liveness(
        intent=bundle.intent,
        plan=ActivationPlanner().plan(
            ObjectiveDeriver().derive(
                Request(
                    mission="Add safe retry behavior to this asynchronous payment worker.",
                    source_context={
                        "pack": "test",
                        "context_signals": [
                            "message_redelivery_possible",
                            "external_side_effect",
                            "multiple_workers",
                        ],
                    },
                )
            ),
            rules_path=(
                valid_pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml"
            ),
            pipeline_path=(valid_pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml"),
        ),
        kernels=KernelResolver().resolve(list(bundle.execution.kernel_activation), valid_pack),
        execution=bundle.execution,
        validation=bundle.validation,
        handoff=bundle.handoff,
        graph=bundle.graph,
    )
    assert report.passed is True
    # INV-CTX-039: every pre-context check still executes, and the context
    # checks execute alongside them. Asserting the set (rather than a count)
    # keeps this honest if the ladder grows again.
    assert set(_ALL_CHECKS) <= set(report.checks)
    assert len(report.checks) == len(_ALL_CHECKS)
