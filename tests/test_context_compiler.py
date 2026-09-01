"""Context compiler law: supersession, scope, kernel needs, gaps, and closure.

Each test here is a discriminator: it pairs the case that must hold with the
neighbouring case that must not, because a selection rule that accepts
everything and a conflict rule that resolves everything both look like passing
code until something is asked to be excluded.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.compiler import context_closure as closure_module
from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.context_closure import (
    CONTEXT_CHECKS,
    ContextClosureValidator,
)
from l9_cognitive_runtime.compiler.context_requirements import ContextRequirementPlanner
from l9_cognitive_runtime.compiler.kernels import KernelBinding, KernelContextNeed
from l9_cognitive_runtime.compiler.task_context import (
    GroupResolution,
    SnapshotResolution,
    resolve_snapshot,
)
from l9_cognitive_runtime.compiler.task_scope import TaskScopeCompiler
from l9_cognitive_runtime.models.context import (
    ApplicableLaw,
    AuthorityContext,
    AuthorityFact,
    AuthorityLevel,
    CapabilityContext,
    CapabilityFact,
    CompiledTaskContext,
    CompilerIdentity,
    ContextBudget,
    ContextItemIdentity,
    ContextKind,
    ContextProvenance,
    ContextRequirement,
    ContextRequirementPlan,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    ContextUnknown,
    CoverageMode,
    DecisionStatus,
    DiscoveryContext,
    EffectiveAuthorityOrderSource,
    FreshnessRequirement,
    GovernedConstraint,
    MissingPolicy,
    PriorDecision,
    UnknownMateriality,
    UnknownReasonCode,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from tests.conftest import intent_for, write_manifest


def source(source_id: str, coordinate: str = "rev-1") -> ContextSourceRef:
    return ContextSourceRef(
        source_id=source_id,
        source_kind="governance",
        locator=f"governance://{source_id}",
        immutable_coordinate=coordinate,
    )


def law(
    law_id: str,
    *,
    supersedes: list[str] | None = None,
    precedence: int | None = None,
    scope_refs: list[str] | None = None,
) -> ApplicableLaw:
    return ApplicableLaw(
        semantic_key=law_id,
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=source(law_id),
        scope_mode=ContextScopeMode.SCOPED if scope_refs else ContextScopeMode.GLOBAL,
        scope_refs=scope_refs or [],
        law_id=law_id,
        statement=f"{law_id} applies",
        precedence=precedence,
        supersedes_refs=supersedes or [],
    )


def decision(
    decision_id: str,
    *,
    status: DecisionStatus = DecisionStatus.ACTIVE,
    supersedes: list[str] | None = None,
    superseded_by: list[str] | None = None,
) -> PriorDecision:
    return PriorDecision(
        semantic_key=decision_id,
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=source(decision_id),
        scope_mode=ContextScopeMode.GLOBAL,
        decision_id=decision_id,
        status=status,
        statement=f"{decision_id} decided",
        supersedes_refs=supersedes or [],
        superseded_by_refs=superseded_by or [],
    )


def constraint(constraint_id: str, *, scope_refs: list[str] | None = None) -> GovernedConstraint:
    return GovernedConstraint(
        semantic_key=constraint_id,
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=source(constraint_id),
        scope_mode=ContextScopeMode.SCOPED if scope_refs else ContextScopeMode.GLOBAL,
        scope_refs=scope_refs or [],
        constraint_id=constraint_id,
        statement=f"{constraint_id} is proven",
    )


def surviving(resolution: SnapshotResolution, kind: ContextKind) -> set[str]:
    """Semantic keys of the given kind that survived into resolvable groups."""
    return {
        semantic_key
        for (kind_value, semantic_key), group in resolution.groups.items()
        if kind_value == kind.value and group.items
    }


# ---------------------------------------------------------------------------
# INV-CTX-013 / INV-CTX-016: supersession is resolved kind-wide.
# ---------------------------------------------------------------------------


def test_a_decision_supersedes_a_differently_identified_decision() -> None:
    snapshot = ContextSnapshot(
        prior_decisions=[decision("ADR_7"), decision("ADR_22", supersedes=["ADR_7"])]
    )
    assert surviving(resolve_snapshot(snapshot), ContextKind.PRIOR_DECISION) == {"ADR_22"}


def test_a_law_supersedes_a_differently_identified_law() -> None:
    snapshot = ContextSnapshot(applicable_law=[law("LAW_1"), law("LAW_2", supersedes=["LAW_1"])])
    assert surviving(resolve_snapshot(snapshot), ContextKind.APPLICABLE_LAW) == {"LAW_2"}


def test_supersession_is_independent_of_input_order() -> None:
    forward = ContextSnapshot(applicable_law=[law("LAW_1"), law("LAW_2", supersedes=["LAW_1"])])
    inverse = ContextSnapshot(applicable_law=[law("LAW_2", supersedes=["LAW_1"]), law("LAW_1")])
    assert surviving(resolve_snapshot(forward), ContextKind.APPLICABLE_LAW) == surviving(
        resolve_snapshot(inverse), ContextKind.APPLICABLE_LAW
    )


def test_a_supersession_chain_leaves_only_the_tip() -> None:
    snapshot = ContextSnapshot(
        applicable_law=[
            law("LAW_1"),
            law("LAW_2", supersedes=["LAW_1"]),
            law("LAW_3", supersedes=["LAW_2"]),
        ]
    )
    assert surviving(resolve_snapshot(snapshot), ContextKind.APPLICABLE_LAW) == {"LAW_3"}


def test_explicit_superseded_status_never_remains_active() -> None:
    snapshot = ContextSnapshot(
        prior_decisions=[decision("ADR_9", status=DecisionStatus.SUPERSEDED), decision("ADR_10")]
    )
    assert surviving(resolve_snapshot(snapshot), ContextKind.PRIOR_DECISION) == {"ADR_10"}


def test_superseded_by_refs_resolve_in_the_inverse_direction() -> None:
    snapshot = ContextSnapshot(
        prior_decisions=[decision("ADR_3", superseded_by=["ADR_4"]), decision("ADR_4")]
    )
    assert surviving(resolve_snapshot(snapshot), ContextKind.PRIOR_DECISION) == {"ADR_4"}


def test_a_supersession_cycle_selects_no_arbitrary_winner() -> None:
    snapshot = ContextSnapshot(
        applicable_law=[
            law("LAW_A", supersedes=["LAW_B"]),
            law("LAW_B", supersedes=["LAW_A"]),
        ]
    )
    resolution = resolve_snapshot(snapshot)
    assert surviving(resolution, ContextKind.APPLICABLE_LAW) == set()
    reasons = {u.reason_code for u in resolution.supersession_unknowns}
    assert UnknownReasonCode.UNKNOWN_SUPERSESSION in reasons
    assert {u.semantic_key for u in resolution.supersession_unknowns} == {"LAW_A", "LAW_B"}


def test_a_cycle_does_not_supersede_a_resolvable_claim_outside_it() -> None:
    snapshot = ContextSnapshot(
        applicable_law=[
            law("LAW_A", supersedes=["LAW_B", "LAW_C"]),
            law("LAW_B", supersedes=["LAW_A"]),
            law("LAW_C"),
        ]
    )
    assert surviving(resolve_snapshot(snapshot), ContextKind.APPLICABLE_LAW) == {"LAW_C"}


def test_a_dangling_supersession_reference_stays_visible() -> None:
    snapshot = ContextSnapshot(applicable_law=[law("LAW_1", supersedes=["LAW_GHOST"])])
    resolution = resolve_snapshot(snapshot)
    assert surviving(resolution, ContextKind.APPLICABLE_LAW) == {"LAW_1"}
    dangling = [
        u
        for u in resolution.supersession_unknowns
        if u.reason_code is UnknownReasonCode.DANGLING_SUPERSESSION
    ]
    assert dangling and dangling[0].details["unresolved_ref"] == "LAW_GHOST"


def test_a_claim_never_supersedes_itself() -> None:
    snapshot = ContextSnapshot(applicable_law=[law("LAW_1", supersedes=["LAW_1"])])
    assert surviving(resolve_snapshot(snapshot), ContextKind.APPLICABLE_LAW) == {"LAW_1"}


# ---------------------------------------------------------------------------
# INV-CTX-014: raw caller hints never prove architecture materiality.
# ---------------------------------------------------------------------------

NEUTRAL_MISSION = "Update the greeting text."


def _compile(
    pack: Path, mission: str, snapshot: ContextSnapshot | None = None, **hints: Any
) -> Any:
    return CognitiveRuntimeService().compile_runtime(
        CompileRequest(
            mission=mission,
            pack_root=pack,
            source_context={"pack": "test", **hints},
        ),
        context_snapshot=snapshot,
    )


def test_the_neutral_mission_fires_no_architecture_materiality(valid_pack: Path) -> None:
    """Guard for the two discriminators below: the mission itself proves nothing."""
    bundle = _compile(valid_pack, NEUTRAL_MISSION)
    assert "OBL.ARCHITECTURE" not in {o.obligation_id for o in bundle.execution.obligations}


def test_a_raw_context_signal_alone_does_not_activate_architecture(valid_pack: Path) -> None:
    bundle = _compile(valid_pack, NEUTRAL_MISSION, context_signals=["multiple_workers"])
    assert "OBL.ARCHITECTURE" not in {o.obligation_id for o in bundle.execution.obligations}
    assert not bundle.task_context.architecture_constraints


def test_the_equivalent_governed_constraint_does_activate_architecture(valid_pack: Path) -> None:
    bundle = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(architecture_constraints=[constraint("multiple_workers")]),
    )
    assert "OBL.ARCHITECTURE" in {o.obligation_id for o in bundle.execution.obligations}
    # And the constraint that proved it survives into the compiled context.
    assert [c.constraint_id for c in bundle.task_context.architecture_constraints] == [
        "multiple_workers"
    ]


def test_irrelevant_governed_context_does_not_move_semantic_identity(valid_pack: Path) -> None:
    """An unrelated *scoped* item is not selected, so it perturbs nothing."""
    base = _compile(valid_pack, NEUTRAL_MISSION, target_refs=["src/greeting"])
    noisy = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(applicable_law=[law("LAW_UNRELATED", scope_refs=["src/elsewhere"])]),
        target_refs=["src/greeting"],
    )
    assert noisy.digests()["context"] == base.digests()["context"]
    assert noisy.digests()["semantic"] == base.digests()["semantic"]


def test_material_governed_context_does_move_semantic_identity(valid_pack: Path) -> None:
    base = _compile(valid_pack, NEUTRAL_MISSION, target_refs=["src/greeting"])
    material = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(applicable_law=[law("LAW_RELEVANT", scope_refs=["src/greeting"])]),
        target_refs=["src/greeting"],
    )
    assert material.digests()["context"] != base.digests()["context"]
    assert material.digests()["semantic"] != base.digests()["semantic"]


# ---------------------------------------------------------------------------
# INV-CTX-015: scoped governing context survives detailed selection.
# ---------------------------------------------------------------------------


def test_a_scoped_constraint_fires_materiality_and_stays_in_the_context(
    valid_pack: Path,
) -> None:
    bundle = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(
            architecture_constraints=[constraint("multiple_workers", scope_refs=["src/greeting"])]
        ),
        target_refs=["src/greeting"],
    )
    assert "OBL.ARCHITECTURE" in {o.obligation_id for o in bundle.execution.obligations}
    assert [c.constraint_id for c in bundle.task_context.architecture_constraints] == [
        "multiple_workers"
    ]


def test_the_same_constraint_scoped_elsewhere_does_neither(valid_pack: Path) -> None:
    bundle = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(
            architecture_constraints=[constraint("multiple_workers", scope_refs=["src/elsewhere"])]
        ),
        target_refs=["src/greeting"],
    )
    assert "OBL.ARCHITECTURE" not in {o.obligation_id for o in bundle.execution.obligations}
    assert not bundle.task_context.architecture_constraints


def test_global_law_applies_to_a_scoped_task(valid_pack: Path) -> None:
    bundle = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(applicable_law=[law("LAW_GLOBAL")]),
        target_refs=["src/greeting"],
    )
    assert [item.law_id for item in bundle.task_context.applicable_law] == ["LAW_GLOBAL"]


def test_unrelated_scoped_law_is_excluded_from_a_scoped_task(valid_pack: Path) -> None:
    bundle = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(applicable_law=[law("LAW_OTHER", scope_refs=["src/elsewhere"])]),
        target_refs=["src/greeting"],
    )
    assert bundle.task_context.applicable_law == []


def test_an_excluded_reference_cannot_select_scoped_context(valid_pack: Path) -> None:
    bundle = _compile(
        valid_pack,
        NEUTRAL_MISSION,
        ContextSnapshot(applicable_law=[law("LAW_LEGACY", scope_refs=["src/legacy"])]),
        target_refs=["src/greeting", "src/legacy"],
        excluded_refs=["src/legacy"],
    )
    assert bundle.task_context.applicable_law == []


# ---------------------------------------------------------------------------
# INV-CTX-020: selected kernels really demand context.
# ---------------------------------------------------------------------------


def binding(source_ref: str, *needs: KernelContextNeed) -> KernelBinding:
    return KernelBinding(
        kernel_id=Path(source_ref).stem,
        source_ref=source_ref,
        source_digest="0" * 64,
        context_needs=needs,
    )


def _plan_for(kernels: list[KernelBinding], *, target_refs: list[str] | None = None) -> Any:
    intent = intent_for(NEUTRAL_MISSION, target_refs=target_refs)
    scope = TaskScopeCompiler().compile(intent)
    discovery = DiscoveryContext(task_scope_digest=scope.sha256())
    activation = ActivationPlan(
        task_summary=NEUTRAL_MISSION,
        matched_route="pack_review",
        confidence="low",
        phase_sequence=["P0_UNPACK"],
        active_kernels=[binding.source_ref for binding in kernels],
        skipped_kernels=[],
        terminal_allowed=False,
        required_outputs=[],
        blockers=[],
        unknowns=[],
        next_phase="P0_UNPACK",
    )
    return ContextRequirementPlanner().plan(intent, scope, discovery, activation, kernels)


LAW_NEED = KernelContextNeed(
    need_id="governing_law",
    context_kind=ContextKind.APPLICABLE_LAW,
    required=True,
    reason="this kernel judges against governing law",
    coverage=CoverageMode.ALL_ELIGIBLE,
    minimum_authority=AuthorityLevel.GOVERNED_VERIFIED,
)


def test_a_kernel_without_needs_adds_no_requirement() -> None:
    plan = _plan_for([binding("runtime/kernels/task/plain.yaml")])
    assert all(not requirement.kernel_need_refs for requirement in plan.requirements)


def test_one_typed_kernel_need_changes_the_requirement_plan() -> None:
    without = _plan_for([binding("runtime/kernels/task/plain.yaml")])
    with_need = _plan_for([binding("runtime/kernels/task/plain.yaml", LAW_NEED)])
    assert with_need.plan_id != without.plan_id
    assert len(with_need.requirements) == len(without.requirements) + 1
    demanded = [r for r in with_need.requirements if r.kernel_need_refs]
    assert len(demanded) == 1
    assert demanded[0].context_kind is ContextKind.APPLICABLE_LAW
    assert demanded[0].required is True
    assert demanded[0].kernel_need_refs == ["runtime/kernels/task/plain.yaml#governing_law"]


def test_identical_needs_from_two_kernels_merge_into_one_requirement() -> None:
    plan = _plan_for(
        [
            binding("runtime/kernels/task/a.yaml", LAW_NEED),
            binding("runtime/kernels/task/b.yaml", LAW_NEED),
        ]
    )
    demanded = [r for r in plan.requirements if r.kernel_need_refs]
    assert len(demanded) == 1
    assert demanded[0].kernel_need_refs == [
        "runtime/kernels/task/a.yaml#governing_law",
        "runtime/kernels/task/b.yaml#governing_law",
    ]


def test_a_kernel_need_binds_to_the_current_task_scope() -> None:
    plan = _plan_for(
        [binding("runtime/kernels/task/plain.yaml", LAW_NEED)],
        target_refs=["src/greeting"],
    )
    demanded = [r for r in plan.requirements if r.kernel_need_refs][0]
    assert demanded.scope_mode is ContextScopeMode.SCOPED
    assert demanded.scope_refs == ["src/greeting"]


def test_a_kernel_declaring_a_need_changes_the_compiled_context(
    tmp_path: Path,
    pack_builder: Any,
) -> None:
    """End to end: the shipped kernel's own source is what carries the need."""
    pack = pack_builder(tmp_path / "pack")
    bundle = _compile(pack, NEUTRAL_MISSION)
    target = next(
        ref for ref in bundle.execution.kernel_activation if ref.endswith((".yaml", ".yml"))
    )
    before = bundle.task_context.provenance.context_requirements_digest

    kernel_path = pack / target
    kernel_path.write_text(
        kernel_path.read_text(encoding="utf-8")
        + "\ncontext_needs:\n"
        + "  - id: governing_law\n"
        + "    context_kind: applicable_law\n"
        + "    required: false\n"
        + "    reason: this kernel reads governing law\n"
        + "    coverage: all_eligible\n"
        + "    minimum_authority: governed_verified\n",
        encoding="utf-8",
    )
    write_manifest(pack)

    after = _compile(pack, NEUTRAL_MISSION)
    assert after.task_context.provenance.context_requirements_digest != before
    assert any(
        need["id"] == "governing_law"
        for kernel in after.task_context.selected_kernels
        for need in kernel["context_needs"]
    )


def test_a_kernel_may_not_declare_task_specific_fields(tmp_path: Path, pack_builder: Any) -> None:
    pack = pack_builder(tmp_path / "pack")
    bundle = _compile(pack, NEUTRAL_MISSION)
    target = next(
        ref for ref in bundle.execution.kernel_activation if ref.endswith((".yaml", ".yml"))
    )
    kernel_path = pack / target
    kernel_path.write_text(
        kernel_path.read_text(encoding="utf-8")
        + "\ncontext_needs:\n"
        + "  - id: overreach\n"
        + "    context_kind: applicable_law\n"
        + "    required: false\n"
        + "    reason: a kernel cannot know the task scope\n"
        + "    coverage: all_eligible\n"
        + "    minimum_authority: governed_verified\n"
        + "    scope_refs: [src/greeting]\n",
        encoding="utf-8",
    )
    write_manifest(pack)
    with pytest.raises(InvalidValueError, match="fields a kernel cannot know"):
        _compile(pack, NEUTRAL_MISSION)


def test_missing_kernel_demanded_context_uses_the_declared_missing_policy() -> None:
    """A required kernel need with nothing to satisfy it preserves an Unknown."""
    plan = _plan_for([binding("runtime/kernels/task/plain.yaml", LAW_NEED)])
    demanded = [r for r in plan.requirements if r.kernel_need_refs][0]
    assert demanded.missing_policy is MissingPolicy.PRESERVE_UNKNOWN
    assert demanded.min_items == 1


# ---------------------------------------------------------------------------
# INV-CTX-021 / INV-CTX-022: required is not available, and never granted.
# ---------------------------------------------------------------------------

MUTATION_MISSION = "Update the greeting text."


def test_a_mutation_task_requires_workspace_mutation(valid_pack: Path) -> None:
    context = _compile(valid_pack, MUTATION_MISSION).task_context
    assert "workspace_mutation" in {r.capability_id for r in context.capabilities.required}


def test_an_empty_snapshot_never_marks_a_required_capability_available(
    valid_pack: Path,
) -> None:
    context = _compile(valid_pack, MUTATION_MISSION).task_context
    assert context.capabilities.available == []
    absent = [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.UNSUPPORTED_CAPABILITY
        and unknown.details.get("capability_id") == "workspace_mutation"
    ]
    assert absent and absent[0].details["state"] == "absent"
    assert absent[0].materiality is UnknownMateriality.NON_BLOCKING


def test_a_capability_proven_unavailable_is_blocking(valid_pack: Path) -> None:
    snapshot = ContextSnapshot(
        capability_facts=[
            CapabilityFact(
                semantic_key="workspace_mutation",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("env"),
                scope_mode=ContextScopeMode.GLOBAL,
                capability_id="workspace_mutation",
                state="unavailable",
            )
        ]
    )
    bundle = _compile(valid_pack, MUTATION_MISSION, snapshot)
    blocking = [
        unknown
        for unknown in bundle.task_context.unresolved_unknowns
        if unknown.details.get("capability_id") == "workspace_mutation"
    ]
    assert blocking and blocking[0].materiality is UnknownMateriality.BLOCKING
    # A blocking context unknown is conserved as a required obligation.
    assert any(
        obligation.obligation_id == f"OBL.EPISTEMIC.CONTEXT.{blocking[0].unknown_id}"
        for obligation in bundle.execution.obligations
    )


def test_required_authority_without_a_grant_stays_visible(valid_pack: Path) -> None:
    context = _compile(valid_pack, MUTATION_MISSION).task_context
    assert "repository_write" in {r.authority_id for r in context.authority.required}
    assert context.authority.granted == []
    gaps = {
        unknown.details.get("authority_id")
        for unknown in context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.MISSING_AUTHORITY
    }
    assert "repository_write" in gaps


def test_the_compiler_default_order_is_not_an_authority_grant(valid_pack: Path) -> None:
    context = _compile(valid_pack, MUTATION_MISSION).task_context
    assert (
        context.authority.effective_order_source is EffectiveAuthorityOrderSource.COMPILER_DEFAULT
    )
    assert context.authority.effective_order  # a precedence order exists
    # ...and it satisfies nothing: the required grant is still recorded as absent.
    absent = [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.details.get("authority_id") == "repository_write"
    ]
    assert absent and absent[0].details["state"] == "absent"


def test_a_proven_grant_closes_the_authority_gap(valid_pack: Path) -> None:
    snapshot = ContextSnapshot(
        authority_facts=[
            AuthorityFact(
                semantic_key="repository_write::",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("grants"),
                scope_mode=ContextScopeMode.GLOBAL,
                authority_id="repository_write",
                state="granted",
            )
        ]
    )
    context = _compile(valid_pack, MUTATION_MISSION, snapshot).task_context
    assert {fact.authority_id for fact in context.authority.granted} == {"repository_write"}
    assert not [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.details.get("authority_id") == "repository_write"
    ]


def test_a_limit_without_a_grant_is_blocking(valid_pack: Path) -> None:
    snapshot = ContextSnapshot(
        authority_facts=[
            AuthorityFact(
                semantic_key="repository_write::",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("grants"),
                scope_mode=ContextScopeMode.GLOBAL,
                authority_id="repository_write",
                state="limit",
            )
        ]
    )
    context = _compile(valid_pack, MUTATION_MISSION, snapshot).task_context
    limited = [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.details.get("authority_id") == "repository_write"
    ]
    assert limited and limited[0].materiality is UnknownMateriality.BLOCKING
    assert limited[0].details["state"] == "limited_without_grant"


# ---------------------------------------------------------------------------
# INV-CTX-025: every closure check proves its name.
# ---------------------------------------------------------------------------


def _requirement(**overrides: Any) -> ContextRequirement:
    payload: dict[str, Any] = {
        "context_kind": ContextKind.APPLICABLE_LAW,
        "reason": "law applicable to the task",
        "required": False,
        "scope_mode": ContextScopeMode.GLOBAL,
        "scope_refs": [],
        "freshness_requirement": FreshnessRequirement.SNAPSHOT_BOUND,
        "coordinate_constraint": None,
        "minimum_authority": AuthorityLevel.INFORMATIVE,
        "priority": 10,
        "coverage_mode": CoverageMode.ALL_ELIGIBLE,
        "min_items": 0,
        "required_semantic_keys": [],
        "max_items": 8,
        "max_bytes": 65_536,
        "missing_policy": MissingPolicy.OPTIONAL,
    }
    payload.update(overrides)
    return ContextRequirement(**payload)


def _context(
    *,
    laws: list[ApplicableLaw],
    unknowns: list[ContextUnknown] | None = None,
) -> CompiledTaskContext:
    scope = TaskScopeCompiler().compile(intent_for(NEUTRAL_MISSION))
    return CompiledTaskContext(
        task_scope=scope,
        applicable_law=laws,
        selected_kernels=[],
        capabilities=CapabilityContext(),
        authority=AuthorityContext(
            effective_order=["user task"],
            effective_order_source=EffectiveAuthorityOrderSource.COMPILER_DEFAULT,
        ),
        unresolved_unknowns=unknowns or [],
        provenance=ContextProvenance(
            task_scope_digest=scope.sha256(),
            discovery_digest="d" * 64,
            context_requirements_digest="r" * 64,
            compiler_identity=CompilerIdentity(package_version="0.0.0", semantics_version="0.0.0"),
        ),
    )


def _plan(requirements: list[ContextRequirement]) -> ContextRequirementPlan:
    return ContextRequirementPlan(
        task_scope_digest="s" * 64,
        matched_route="pack_review",
        global_budget=ContextBudget(max_total_items=64, max_total_bytes=262_144),
        requirements=requirements,
    )


def test_a_per_requirement_item_breach_is_detected_while_the_global_budget_passes() -> None:
    requirement = _requirement(max_items=1)
    laws = [
        law("LAW_1").model_copy(update={"selected_because": [requirement.requirement_id]}),
        law("LAW_2").model_copy(update={"selected_because": [requirement.requirement_id]}),
    ]
    context = _context(laws=laws)
    # The global budget is nowhere near exhausted; only the requirement's own is.
    assert len(context.selected_items()) < 64
    with pytest.raises(InvalidValueError, match="per_requirement_and_global_budgets"):
        ContextClosureValidator().validate(
            context=context,
            requirement_plan=_plan([requirement]),
            resolution=SnapshotResolution(groups={}),
            kernels=[],
        )


def test_a_per_requirement_byte_breach_is_detected_while_the_global_budget_passes() -> None:
    requirement = _requirement(max_bytes=64)
    laws = [law("LAW_1").model_copy(update={"selected_because": [requirement.requirement_id]})]
    with pytest.raises(InvalidValueError, match="per_requirement_and_global_budgets"):
        ContextClosureValidator().validate(
            context=_context(laws=laws),
            requirement_plan=_plan([requirement]),
            resolution=SnapshotResolution(groups={}),
            kernels=[],
        )


def test_a_within_budget_context_passes_the_same_check() -> None:
    requirement = _requirement(max_items=4)
    laws = [law("LAW_1").model_copy(update={"selected_because": [requirement.requirement_id]})]
    report = ContextClosureValidator().validate(
        context=_context(laws=laws),
        requirement_plan=_plan([requirement]),
        resolution=SnapshotResolution(groups={}),
        kernels=[],
    )
    assert report.passed and report.checks == CONTEXT_CHECKS


def test_a_conflict_that_vanished_entirely_is_still_detected() -> None:
    """The conflicting key is in *no* selected item — the case a selected-set
    check cannot see."""
    requirement = _requirement()
    contenders: list[ContextItemIdentity] = [law("LAW_X"), law("LAW_X")]
    resolution = SnapshotResolution(
        groups={
            ("applicable_law", "LAW_X"): GroupResolution(
                [], conflict=True, details={"claims": 2}, sources=contenders
            )
        }
    )
    context = _context(laws=[])
    assert not any(item.semantic_key == "LAW_X" for item in context.selected_items())
    with pytest.raises(InvalidValueError, match="no_equal_authority_conflict_is_silently_selected"):
        ContextClosureValidator().validate(
            context=context,
            requirement_plan=_plan([requirement]),
            resolution=resolution,
            kernels=[],
        )


def test_a_conflict_disposed_as_an_unknown_passes() -> None:
    requirement = _requirement()
    resolution = SnapshotResolution(
        groups={
            ("applicable_law", "LAW_X"): GroupResolution(
                [], conflict=True, details={"claims": 2}, sources=[law("LAW_X"), law("LAW_X")]
            )
        }
    )
    disposition = ContextUnknown(
        requirement_ref=requirement.requirement_id,
        semantic_key="LAW_X",
        reason_code=UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS,
        materiality=UnknownMateriality.NON_BLOCKING,
        details={"context_kind": "applicable_law", "claims": 2},
    )
    report = ContextClosureValidator().validate(
        context=_context(laws=[], unknowns=[disposition]),
        requirement_plan=_plan([requirement]),
        resolution=resolution,
        kernels=[],
    )
    assert report.passed


def test_a_conflict_no_requirement_would_have_matched_is_not_charged() -> None:
    """Eligibility is judged with the compiler's own matching rule."""
    requirement = _requirement(minimum_authority=AuthorityLevel.GOVERNED_AUTHORITATIVE)
    off_scope = law("LAW_Y", scope_refs=["src/elsewhere"])
    resolution = SnapshotResolution(
        groups={
            ("applicable_law", "LAW_Y"): GroupResolution(
                [], conflict=True, details={"claims": 2}, sources=[off_scope, off_scope]
            )
        }
    )
    report = ContextClosureValidator().validate(
        context=_context(laws=[]),
        requirement_plan=_plan(
            [
                _requirement(
                    scope_mode=ContextScopeMode.GLOBAL,
                    minimum_authority=requirement.minimum_authority,
                )
            ]
        ),
        resolution=resolution,
        kernels=[],
    )
    assert report.passed


def test_removing_a_closure_check_from_execution_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared check that does not run is a failure, not a shorter report."""
    monkeypatch.setattr(
        closure_module, "CONTEXT_CHECKS", (*CONTEXT_CHECKS, "a_check_nobody_implemented")
    )
    with pytest.raises(InvalidValueError, match="context_closure_ladder_is_complete"):
        ContextClosureValidator().validate(
            context=_context(laws=[]),
            requirement_plan=_plan([_requirement()]),
            resolution=SnapshotResolution(groups={}),
            kernels=[],
        )


def test_a_stale_item_identity_is_detected_by_closure() -> None:
    """A claim mutated after construction leaves identity behind; closure sees it.

    The model layer refuses to *build* such an item, so the tamper is applied by
    writing straight into ``__dict__`` — the one route that bypasses validation
    and therefore the one closure has to catch on its own.
    """
    requirement = _requirement()
    item = law("LAW_1").model_copy(update={"selected_because": [requirement.requirement_id]})
    context = _context(laws=[item])
    context.applicable_law[0].__dict__["statement"] = "quietly rewritten after identity was derived"
    with pytest.raises(InvalidValueError, match="every_selected_item_identity_matches_kind_recipe"):
        ContextClosureValidator().validate(
            context=context,
            requirement_plan=_plan([requirement]),
            resolution=SnapshotResolution(groups={}),
            kernels=[],
        )


def test_an_unbound_selected_item_is_detected_by_closure() -> None:
    with pytest.raises(InvalidValueError, match="every_selected_item_has_relevance_binding"):
        ContextClosureValidator().validate(
            context=_context(laws=[law("LAW_1")]),
            requirement_plan=_plan([_requirement()]),
            resolution=SnapshotResolution(groups={}),
            kernels=[],
        )


def test_an_undisposed_required_capability_is_detected_by_closure(valid_pack: Path) -> None:
    """Dropping the recorded gap must not read as 'no gap'."""
    from l9_cognitive_runtime.compiler.kernels import KernelResolver

    bundle = _compile(valid_pack, MUTATION_MISSION)
    context = bundle.task_context
    kernels = KernelResolver().resolve(list(bundle.execution.kernel_activation), valid_pack)
    stripped = copy.deepcopy(context).model_copy(
        update={
            "unresolved_unknowns": [
                unknown
                for unknown in context.unresolved_unknowns
                if unknown.reason_code is not UnknownReasonCode.UNSUPPORTED_CAPABILITY
            ]
        }
    )
    assert stripped.capabilities.required
    with pytest.raises(InvalidValueError, match="capability_and_authority_gaps_are_explicit"):
        ContextClosureValidator().validate(
            context=stripped,
            requirement_plan=_plan([_requirement()]),
            resolution=SnapshotResolution(groups={}),
            kernels=kernels,
        )
