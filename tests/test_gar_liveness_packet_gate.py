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
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.compiler import pipeline as pipeline_module
from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.context_closure import CONTEXT_CHECKS, ContextClosureReport
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.liveness import (
    _ALL_CHECKS,
    LivenessReport,
    validate_runtime_semantic_liveness,
)
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.pipeline import CompilePipeline
from l9_cognitive_runtime.models.context import (
    ApplicableLaw,
    AuthorityLevel,
    CompiledTaskContext,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    UnknownReasonCode,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle
from tests.conftest import discovery_for, empty_discovery, governed_signal_snapshot

ROOT = Path(__file__).resolve().parents[1]

MISSION = "Add safe retry behavior to this asynchronous payment worker."
# INV-CTX-014: the same architecture signals, proven as governed constraints
# rather than asserted as raw ``source_context`` hints.
GOVERNED_SIGNALS = (
    "message_redelivery_possible",
    "external_side_effect",
    "multiple_workers",
)


def _snapshot() -> ContextSnapshot:
    return governed_signal_snapshot(*GOVERNED_SIGNALS)


def _request(pack: Path) -> CompileRequest:
    return CompileRequest(mission=MISSION, pack_root=pack, source_context={"pack": "test"})


def _compile(pack: Path, snapshot: ContextSnapshot | None = None) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(
        _request(pack), context_snapshot=snapshot if snapshot is not None else _snapshot()
    )


def _run_liveness(
    bundle: RuntimeBundle,
    pack: Path,
    packet: dict[str, Any],
    *,
    snapshot: ContextSnapshot | None = None,
    task_context: CompiledTaskContext | None = None,
) -> LivenessReport:
    intent = ObjectiveDeriver().derive(_request(pack))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
        discovery=discovery_for(intent, snapshot if snapshot is not None else _snapshot()),
    )
    context_digest = bundle.digests()["context"]
    return validate_runtime_semantic_liveness(
        intent=bundle.intent,
        plan=plan,
        kernels=KernelResolver().resolve(list(bundle.execution.kernel_activation), pack),
        execution=bundle.execution,
        validation=bundle.validation,
        handoff=bundle.handoff,
        graph=bundle.graph,
        task_context=task_context if task_context is not None else bundle.task_context,
        context_digest=context_digest,
        # The closure ladder has its own suite; here it is a passing fixture so
        # what fails or passes is the packet check under test.
        closure_report=ContextClosureReport(checks=CONTEXT_CHECKS, passed=True),
        packet=packet,
        semantic_payload={"context_digest": context_digest},
    )


def test_liveness_detects_packet_dropping_blocking_obligation(valid_pack: Path) -> None:
    """A packet missing a required blocking obligation must fail closed."""
    bundle = _compile(valid_pack)
    weakened = copy.deepcopy(bundle.packet)
    dropped = weakened["required_obligations"].pop()
    assert dropped["obligation_id"]
    with pytest.raises(InvalidValueError, match="no_adapter_drops_blocking_obligation"):
        _run_liveness(bundle, valid_pack, weakened)


def test_liveness_accepts_the_live_packet(valid_pack: Path) -> None:
    bundle = _compile(valid_pack)
    report = _run_liveness(bundle, valid_pack, bundle.packet)
    assert report.passed


def test_liveness_executes_every_declared_check(valid_pack: Path) -> None:
    """Coverage is enforced: a declared check may never silently not run."""
    bundle = _compile(valid_pack)
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
    _compile(valid_pack)
    assert seen, "validate_packet was never called on the compile path"


# ---------------------------------------------------------------------------
# F-005: `no_unresolved_equal_authority_conflict_is_silently_selected` keys a
# conflict by (context_kind, semantic_key). Semantic keys are only unique
# within a kind — a constraint's key is its constraint_id and a law's key is
# its law_id — so a key-only check charged an unrelated selected constraint
# with a law conflict that merely shared its spelling.
# ---------------------------------------------------------------------------

CONTESTED_KEY = GOVERNED_SIGNALS[0]


def _contested_law(statement: str, source_id: str, key: str) -> ApplicableLaw:
    return ApplicableLaw(
        semantic_key=key,
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=ContextSourceRef(
            source_id=source_id,
            source_kind="governance",
            locator=f"governance://{source_id}",
            immutable_coordinate="rev-1",
        ),
        scope_mode=ContextScopeMode.GLOBAL,
        law_id=key,
        statement=statement,
    )


def _snapshot_with_law_conflict(key: str) -> ContextSnapshot:
    """The governed signals plus two equal-authority laws contradicting on ``key``."""
    return _snapshot().model_copy(
        update={
            "applicable_law": [
                _contested_law(f"{key} says A", f"{key}-a", key),
                _contested_law(f"{key} says B", f"{key}-b", key),
            ]
        }
    )


def _law_conflicts(bundle: RuntimeBundle, key: str) -> list[dict[str, Any]]:
    return [
        unknown.details
        for unknown in bundle.task_context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS
        and unknown.semantic_key == key
    ]


def _force_selected_law(bundle: RuntimeBundle, key: str) -> CompiledTaskContext:
    """The compiled context with one side of the ``key`` law conflict selected anyway."""
    forced = _contested_law(f"{key} says A", f"{key}-a", key).model_copy(
        update={"selected_because": ["forced-by-test"]}
    )
    return bundle.task_context.model_copy(
        update={"applicable_law": [*bundle.task_context.applicable_law, forced]}
    )


def test_law_conflict_does_not_charge_a_selected_constraint_sharing_its_key(
    valid_pack: Path,
) -> None:
    """RG-005a: a law conflict on K beside a selected constraint K compiles."""
    snapshot = _snapshot_with_law_conflict(CONTESTED_KEY)
    bundle = _compile(valid_pack, snapshot)
    assert CONTESTED_KEY in {
        item.constraint_id for item in bundle.task_context.architecture_constraints
    }
    conflicts = _law_conflicts(bundle, CONTESTED_KEY)
    assert conflicts, "the law conflict must stay visible as an Unknown"
    assert {details["context_kind"] for details in conflicts} == {"applicable_law"}
    assert not any(law.law_id == CONTESTED_KEY for law in bundle.task_context.applicable_law)
    report = _run_liveness(bundle, valid_pack, bundle.packet, snapshot=snapshot)
    assert report.checks == _ALL_CHECKS


def test_selected_law_on_a_conflicted_law_key_still_fails_liveness(valid_pack: Path) -> None:
    """RG-005b: the same-kind silently selected conflict remains a liveness breach."""
    key = "LAW_CONTESTED"
    snapshot = _snapshot_with_law_conflict(key)
    bundle = _compile(valid_pack, snapshot)
    assert _law_conflicts(bundle, key)
    with pytest.raises(
        InvalidValueError, match="no_unresolved_equal_authority_conflict_is_silently_selected"
    ):
        _run_liveness(
            bundle,
            valid_pack,
            bundle.packet,
            snapshot=snapshot,
            task_context=_force_selected_law(bundle, key),
        )


def test_conflict_unknown_without_context_kind_matches_every_kind(valid_pack: Path) -> None:
    """A conflict whose kind cannot be read fails closed against any selected key."""
    snapshot = _snapshot_with_law_conflict(CONTESTED_KEY)
    bundle = _compile(valid_pack, snapshot)
    kindless = [
        unknown.model_copy(
            update={"details": {k: v for k, v in unknown.details.items() if k != "context_kind"}}
        )
        if unknown.reason_code is UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS
        else unknown
        for unknown in bundle.task_context.unresolved_unknowns
    ]
    with pytest.raises(
        InvalidValueError, match="no_unresolved_equal_authority_conflict_is_silently_selected"
    ):
        _run_liveness(
            bundle,
            valid_pack,
            bundle.packet,
            snapshot=snapshot,
            task_context=bundle.task_context.model_copy(update={"unresolved_unknowns": kindless}),
        )


# ---------------------------------------------------------------------------
# F-006: `every_required_execution_obligation_has_realization_path` compared
# required pending obligations with graph.obligation_refs, which the graph
# copies from the same contract — so it held for any contract. The realized
# set is now what the graph nodes actually carry.
# ---------------------------------------------------------------------------


def test_supplied_plan_without_p0_fails_realization_path_liveness() -> None:
    """RG-006a: an activation plan that drops the only phase realizing an
    obligation fails closed, naming the obligation no node carries."""
    mission = "compile a kernel contract"
    intent = ObjectiveDeriver().derive(CompileRequest(mission=mission))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=ROOT / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=ROOT / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
        discovery=empty_discovery(intent),
    )
    assert plan.matched_route == "prompt_or_kernel_compilation"
    assert "P0_UNPACK" in plan.phase_sequence
    # The router's own plan realizes every obligation (control).
    CompilePipeline().compile_from_root(ROOT, plan.task_summary, activation_plan=plan)

    without_p0 = dataclasses.replace(
        plan, phase_sequence=[phase for phase in plan.phase_sequence if phase != "P0_UNPACK"]
    )
    with pytest.raises(
        InvalidValueError, match="every_required_execution_obligation_has_realization_path"
    ) as excinfo:
        CompilePipeline().compile_from_root(
            ROOT, without_p0.task_summary, activation_plan=without_p0
        )
    assert excinfo.value.details["missing"] == ["OBL.EPISTEMIC.REALIZATION_RESOLUTION"]
