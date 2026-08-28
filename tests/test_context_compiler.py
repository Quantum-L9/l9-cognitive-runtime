"""Deterministic context compilation law.

Covers the selection, conflict, budget, coverage, and determinism acceptance
criteria (A009-A012, A017-A031, A034-A035, A052-A054, A060, A064). Every test
here exercises the compiler directly so a failure names the algorithm, not the
pipeline around it.
"""

from __future__ import annotations

from typing import Any

import pytest

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.context_closure import ContextClosureValidator
from l9_cognitive_runtime.compiler.context_requirements import ContextRequirementPlanner
from l9_cognitive_runtime.compiler.execution import AUTHORITY_ORDER
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.task_context import (
    ContextCompiler,
    ContextDiscoveryCompiler,
    resolve_snapshot,
)
from l9_cognitive_runtime.compiler.task_scope import TaskScopeCompiler
from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.context import (
    ApplicableLaw,
    AuthorityFact,
    AuthorityLevel,
    CapabilityFact,
    CompiledTaskContext,
    ContextBudget,
    ContextKind,
    ContextRequirement,
    ContextRequirementPlan,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    CoverageMode,
    DecisionStatus,
    DependencyContext,
    EffectiveAuthorityOrderSource,
    EntityContext,
    FreshnessRequirement,
    GovernedConstraint,
    MemoryContext,
    MissingPolicy,
    PriorDecision,
    RepositoryState,
    UnknownMateriality,
    UnknownReasonCode,
    canonical_cost,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.types import CompileRequest

# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------

KERNELS = [
    KernelBinding(
        kernel_id="repo_auditor",
        source_ref="kernels/repo_auditor.yaml",
        source_digest="a" * 64,
    )
]


def src(source_id: str = "s1", coordinate: str | None = "rev-1") -> ContextSourceRef:
    return ContextSourceRef(
        source_id=source_id,
        source_kind="repository",
        locator=f"repo://l9/{source_id}",
        immutable_coordinate=coordinate,
    )


def fact(
    item_id: str,
    *,
    subject: str = "src/a.py",
    fact_type: str = "owner",
    value: Any = "team-a",
    authority: AuthorityLevel = AuthorityLevel.GOVERNED_AUTHORITATIVE,
    revision: str = "rev-1",
    scope_refs: tuple[str, ...] = ("src/a.py",),
    source_id: str = "s1",
) -> RepositoryState:
    return RepositoryState(
        item_id=item_id,
        semantic_key=f"l9:{subject}:{fact_type}",
        authority_level=authority,
        source_ref=src(source_id),
        scope_mode=ContextScopeMode.SCOPED if scope_refs else ContextScopeMode.GLOBAL,
        scope_refs=list(scope_refs),
        repository_id="l9",
        revision=revision,
        subject_ref=subject,
        fact_type=fact_type,
        value=value,
    )


def law(
    item_id: str,
    law_id: str,
    *,
    statement: str = "governed",
    precedence: int | None = None,
    supersedes: tuple[str, ...] = (),
    authority: AuthorityLevel = AuthorityLevel.GOVERNED_AUTHORITATIVE,
) -> ApplicableLaw:
    return ApplicableLaw(
        item_id=item_id,
        semantic_key=law_id,
        authority_level=authority,
        source_ref=src(item_id),
        scope_mode=ContextScopeMode.GLOBAL,
        law_id=law_id,
        statement=statement,
        precedence=precedence,
        supersedes_refs=list(supersedes),
    )


def decision(
    item_id: str,
    decision_id: str,
    status: DecisionStatus,
    *,
    statement: str = "d",
    supersedes: tuple[str, ...] = (),
) -> PriorDecision:
    return PriorDecision(
        item_id=item_id,
        semantic_key=decision_id,
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=src(item_id),
        scope_mode=ContextScopeMode.GLOBAL,
        decision_id=decision_id,
        status=status,
        statement=statement,
        supersedes_refs=list(supersedes),
    )


def memory(item_id: str, memory_id: str, content: Any = "recalled") -> MemoryContext:
    return MemoryContext(
        item_id=item_id,
        semantic_key=memory_id,
        authority_level=AuthorityLevel.INFORMATIVE,
        source_ref=src(item_id, coordinate=None),
        scope_mode=ContextScopeMode.GLOBAL,
        memory_id=memory_id,
        memory_kind="recall",
        content=content,
        relevance_reason="prior work on this file",
    )


def activation_plan(**overrides: Any) -> ActivationPlan:
    data: dict[str, Any] = {
        "task_summary": "summary",
        "matched_route": "pack_review",
        "confidence": "high",
        "phase_sequence": ["P0_UNPACK"],
        "active_kernels": ["kernels/repo_auditor.yaml"],
        "skipped_kernels": [],
        "terminal_allowed": False,
        "required_outputs": [],
        "blockers": [],
        "unknowns": [],
        "next_phase": "P0_UNPACK",
        "architecture_materiality": {"required": False},
    }
    data.update(overrides)
    return ActivationPlan(**data)


def intent_for(mission: str, **source_context: Any) -> IntentContract:
    return ObjectiveDeriver().derive(
        CompileRequest(
            mission=mission,
            source_context={"pack": "l9_cognitive_runtime", **source_context},
        )
    )


def requirement(**overrides: Any) -> ContextRequirement:
    data: dict[str, Any] = {
        "context_kind": ContextKind.REPOSITORY_STATE,
        "reason": "task names this subject",
        "required": True,
        "scope_mode": ContextScopeMode.SCOPED,
        "scope_refs": ["src/a.py"],
        "freshness_requirement": FreshnessRequirement.SNAPSHOT_BOUND,
        "minimum_authority": AuthorityLevel.GOVERNED_VERIFIED,
        "priority": 10,
        "coverage_mode": CoverageMode.ALL_ELIGIBLE,
        "min_items": 1,
        "max_items": 8,
        "max_bytes": 65_536,
        "missing_policy": MissingPolicy.PRESERVE_UNKNOWN,
    }
    data.update(overrides)
    return ContextRequirement(**data)


def compile_context(
    snapshot: ContextSnapshot,
    requirements: list[ContextRequirement],
    *,
    mission: str = "Update the payment module owner record.",
    hints: dict[str, Any] | None = None,
    plan: ActivationPlan | None = None,
    budget: ContextBudget | None = None,
) -> CompiledTaskContext:
    intent = intent_for(mission, **(hints or {"target_refs": ["src/a.py"]}))
    scope = TaskScopeCompiler().compile(intent)
    resolutions = resolve_snapshot(snapshot)
    discovery = ContextDiscoveryCompiler().compile(scope, snapshot, resolutions)
    activation = plan or activation_plan()
    requirement_plan = ContextRequirementPlan(
        task_scope_digest=scope.sha256(),
        matched_route=activation.matched_route,
        global_budget=budget or ContextBudget(max_total_items=64, max_total_bytes=262_144),
        requirements=requirements,
    )
    return ContextCompiler().compile(
        intent=intent,
        scope=scope,
        snapshot=snapshot,
        resolutions=resolutions,
        discovery=discovery,
        requirement_plan=requirement_plan,
        activation=activation,
        kernels=KERNELS,
        package_version="0.1.0",
        default_authority_order=AUTHORITY_ORDER,
    )


def unknown_codes(context: CompiledTaskContext) -> set[str]:
    return {unknown.reason_code.value for unknown in context.unresolved_unknowns}


# --------------------------------------------------------------------------
# A009 / A013: every selected item traces to a requirement.
# --------------------------------------------------------------------------


def test_every_selected_item_carries_its_requirement_binding() -> None:
    req = requirement()
    context = compile_context(ContextSnapshot(repository_state=[fact("f1")]), [req])
    assert [item.item_id for item in context.repository_state] == ["f1"]
    assert context.repository_state[0].selected_because == [req.requirement_id]


def test_an_item_reused_by_two_requirements_records_both() -> None:
    left = requirement(reason="first reason", priority=10)
    right = requirement(reason="second reason", priority=20)
    context = compile_context(ContextSnapshot(repository_state=[fact("f1")]), [left, right])
    assert context.repository_state[0].selected_because == sorted(
        [left.requirement_id, right.requirement_id]
    )


# --------------------------------------------------------------------------
# A011 / A012 / A021: irrelevance and input order do not move semantics.
# --------------------------------------------------------------------------


def test_irrelevant_snapshot_items_are_excluded_deterministically() -> None:
    relevant = fact("f1")
    irrelevant = fact("f2", subject="docs/unrelated.md", scope_refs=("docs/unrelated.md",))
    context = compile_context(
        ContextSnapshot(repository_state=[relevant, irrelevant]), [requirement()]
    )
    assert [item.item_id for item in context.repository_state] == ["f1"]


def test_adding_an_irrelevant_item_does_not_change_the_context_digest() -> None:
    req = requirement()
    lean = compile_context(ContextSnapshot(repository_state=[fact("f1")]), [req])
    noisy = compile_context(
        ContextSnapshot(
            repository_state=[
                fact("f1"),
                fact("f9", subject="docs/unrelated.md", scope_refs=("docs/unrelated.md",)),
            ],
            memory_context=[memory("m9", "irrelevant-memory")],
        ),
        [req],
    )
    assert lean.sha256() == noisy.sha256()


def test_permuting_snapshot_lists_does_not_change_the_context_digest() -> None:
    req = requirement(scope_refs=["src/a.py", "src/b.py"])
    items = [
        fact("f1", fact_type="owner"),
        fact("f2", fact_type="language"),
        fact("f3", subject="src/b.py", fact_type="owner", scope_refs=("src/b.py",)),
    ]
    forward = compile_context(
        ContextSnapshot(repository_state=items),
        [req],
        hints={"target_refs": ["src/a.py", "src/b.py"]},
    )
    backward = compile_context(
        ContextSnapshot(repository_state=list(reversed(items))),
        [req],
        hints={"target_refs": ["src/b.py", "src/a.py"]},
    )
    assert forward.sha256() == backward.sha256()


# --------------------------------------------------------------------------
# A022: deterministic deduplication.
# --------------------------------------------------------------------------


def test_semantically_identical_duplicates_collapse_to_one_item() -> None:
    twin_a = fact("f-aaa", source_id="s1")
    twin_b = fact("f-bbb", source_id="s2")
    context = compile_context(ContextSnapshot(repository_state=[twin_b, twin_a]), [requirement()])
    assert len(context.repository_state) == 1
    # The representative is chosen by coordinate/digest/id order, never by
    # which one appeared first in the caller's list.
    assert context.repository_state[0].item_id == "f-aaa"


def test_duplicate_representative_prefers_stronger_authority() -> None:
    weak = fact("f-aaa", authority=AuthorityLevel.GOVERNED_VERIFIED)
    strong = fact("f-zzz", authority=AuthorityLevel.GOVERNED_AUTHORITATIVE)
    context = compile_context(ContextSnapshot(repository_state=[weak, strong]), [requirement()])
    assert len(context.repository_state) == 1
    assert context.repository_state[0].item_id == "f-zzz"


# --------------------------------------------------------------------------
# A020: conflicts resolve by domain rule, never by list order.
# --------------------------------------------------------------------------


def test_equal_authority_contradiction_becomes_an_unknown_not_a_choice() -> None:
    left = fact("f1", value="team-a")
    right = fact("f2", value="team-b")
    forward = compile_context(ContextSnapshot(repository_state=[left, right]), [requirement()])
    backward = compile_context(ContextSnapshot(repository_state=[right, left]), [requirement()])
    assert forward.repository_state == []
    assert backward.repository_state == []
    assert UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS.value in unknown_codes(forward)
    assert forward.sha256() == backward.sha256()


def test_stronger_governed_authority_wins_at_the_same_revision() -> None:
    weak = fact("f1", value="team-a", authority=AuthorityLevel.GOVERNED_VERIFIED)
    strong = fact("f2", value="team-b", authority=AuthorityLevel.GOVERNED_AUTHORITATIVE)
    context = compile_context(ContextSnapshot(repository_state=[weak, strong]), [requirement()])
    assert [item.value for item in context.repository_state] == ["team-b"]


def test_differing_revisions_do_not_imply_recency() -> None:
    old = fact("f1", value="team-a", revision="rev-1")
    new = fact("f2", value="team-b", revision="rev-2")
    context = compile_context(ContextSnapshot(repository_state=[old, new]), [requirement()])
    assert context.repository_state == []
    assert UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS.value in unknown_codes(context)


def test_dependency_version_difference_does_not_imply_latest() -> None:
    req = requirement(
        context_kind=ContextKind.DEPENDENCY_CONTEXT,
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
    )

    def dependency(item_id: str, version: str) -> DependencyContext:
        return DependencyContext(
            item_id=item_id,
            semantic_key="pydantic:upstream:runtime:src/a.py",
            authority_level=AuthorityLevel.GOVERNED_VERIFIED,
            source_ref=src(item_id),
            scope_mode=ContextScopeMode.SCOPED,
            scope_refs=["src/a.py"],
            dependency_id="pydantic",
            relationship="runtime",
            direction="upstream",
            target_ref="src/a.py",
            version_or_revision=version,
        )

    context = compile_context(
        ContextSnapshot(dependency_context=[dependency("d1", "2.8"), dependency("d2", "2.9")]),
        [req],
    )
    assert context.dependency_context == []
    assert UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS.value in unknown_codes(context)


def test_explicit_law_supersession_wins_before_numeric_precedence() -> None:
    req = requirement(
        context_kind=ContextKind.APPLICABLE_LAW,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
    )
    old = law("l1", "LAW-1", statement="old", precedence=0)
    # Same key, different claim: the newer one explicitly supersedes it.
    new = law("l2", "LAW-1", statement="new", precedence=9, supersedes=("LAW-1",))
    context = compile_context(ContextSnapshot(applicable_law=[old, new]), [req])
    assert [item.statement for item in context.applicable_law] == ["new"]


def test_lower_numeric_precedence_is_stronger_when_both_declare_it() -> None:
    req = requirement(
        context_kind=ContextKind.APPLICABLE_LAW,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
    )
    weak = law("l1", "LAW-1", statement="weak", precedence=5)
    strong = law("l2", "LAW-1", statement="strong", precedence=1)
    context = compile_context(ContextSnapshot(applicable_law=[weak, strong]), [req])
    assert [item.statement for item in context.applicable_law] == ["strong"]


# --------------------------------------------------------------------------
# A017 / A018: law is selected not dumped; decisions preserve supersession.
# --------------------------------------------------------------------------


def test_irrelevant_scoped_law_is_not_selected() -> None:
    req = requirement(
        context_kind=ContextKind.APPLICABLE_LAW,
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
        scope_mode=ContextScopeMode.SCOPED,
        scope_refs=["src/a.py"],
    )
    applicable = ApplicableLaw(
        item_id="l1",
        semantic_key="LAW-APPLIES",
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=src("l1"),
        scope_mode=ContextScopeMode.SCOPED,
        scope_refs=["src/a.py"],
        law_id="LAW-APPLIES",
        statement="applies here",
    )
    elsewhere = ApplicableLaw(
        item_id="l2",
        semantic_key="LAW-ELSEWHERE",
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=src("l2"),
        scope_mode=ContextScopeMode.SCOPED,
        scope_refs=["infra/terraform"],
        law_id="LAW-ELSEWHERE",
        statement="applies elsewhere",
    )
    context = compile_context(ContextSnapshot(applicable_law=[applicable, elsewhere]), [req])
    assert [item.law_id for item in context.applicable_law] == ["LAW-APPLIES"]


def test_superseded_decision_does_not_remain_active() -> None:
    req = requirement(
        context_kind=ContextKind.PRIOR_DECISION,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
    )
    context = compile_context(
        ContextSnapshot(
            prior_decisions=[
                decision("d1", "ADR-1", DecisionStatus.SUPERSEDED),
                decision("d2", "ADR-2", DecisionStatus.ACTIVE),
            ]
        ),
        [req],
    )
    assert [item.decision_id for item in context.prior_decisions] == ["ADR-2"]


def test_superseded_decision_is_retained_when_it_explains_lineage() -> None:
    req = requirement(
        context_kind=ContextKind.PRIOR_DECISION,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
    )
    context = compile_context(
        ContextSnapshot(
            prior_decisions=[
                decision("d1", "ADR-1", DecisionStatus.SUPERSEDED),
                decision("d2", "ADR-2", DecisionStatus.ACTIVE, supersedes=("ADR-1",)),
            ]
        ),
        [req],
    )
    assert {item.decision_id for item in context.prior_decisions} == {"ADR-1", "ADR-2"}


def test_unknown_supersession_stays_an_unknown() -> None:
    req = requirement(
        context_kind=ContextKind.PRIOR_DECISION,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
    )
    context = compile_context(
        ContextSnapshot(prior_decisions=[decision("d1", "ADR-7", DecisionStatus.UNKNOWN)]), [req]
    )
    assert UnknownReasonCode.UNKNOWN_SUPERSESSION.value in unknown_codes(context)
    material = [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.UNKNOWN_SUPERSESSION
    ]
    assert material[0].materiality is UnknownMateriality.BLOCKING


# --------------------------------------------------------------------------
# A019: memory is enrichment, never operational truth.
# --------------------------------------------------------------------------


def test_memory_cannot_override_a_governed_repository_claim() -> None:
    governed = requirement()
    memory_requirement = requirement(
        context_kind=ContextKind.MEMORY_CONTEXT,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
        minimum_authority=AuthorityLevel.INFORMATIVE,
        coverage_mode=CoverageMode.MINIMUM,
        required=False,
        min_items=2,
        missing_policy=MissingPolicy.OPTIONAL,
        priority=90,
    )
    # The memory asserts the opposite of the governed fact, under the same
    # human-readable subject. It is a different context kind, so it can never
    # enter the same conflict group.
    context = compile_context(
        ContextSnapshot(
            repository_state=[fact("f1", value="team-a")],
            memory_context=[memory("m1", "l9:src/a.py:owner", content="team-zzz")],
        ),
        [governed, memory_requirement],
    )
    assert [item.value for item in context.repository_state] == ["team-a"]
    assert [item.memory_id for item in context.memory_context] == ["l9:src/a.py:owner"]
    assert context.memory_context[0].authority_level is AuthorityLevel.INFORMATIVE


# --------------------------------------------------------------------------
# A023: BLOCK / PRESERVE_UNKNOWN / OPTIONAL behave distinctly.
# --------------------------------------------------------------------------


def test_block_policy_fails_the_compile_closed() -> None:
    with pytest.raises(InvalidValueError, match="BLOCK missing policy"):
        compile_context(ContextSnapshot.empty(), [requirement(missing_policy=MissingPolicy.BLOCK)])


def test_preserve_unknown_policy_continues_with_a_bound_unknown() -> None:
    req = requirement(missing_policy=MissingPolicy.PRESERVE_UNKNOWN)
    context = compile_context(ContextSnapshot.empty(), [req])
    unknowns = [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.requirement_ref == req.requirement_id
    ]
    assert len(unknowns) == 1
    assert unknowns[0].reason_code is UnknownReasonCode.MISSING_REQUIRED_CONTEXT
    assert unknowns[0].materiality is UnknownMateriality.BLOCKING


def test_optional_policy_neither_blocks_nor_creates_an_unknown() -> None:
    req = requirement(required=False, min_items=0, missing_policy=MissingPolicy.OPTIONAL)
    context = compile_context(ContextSnapshot.empty(), [req])
    assert context.repository_state == []
    assert [
        unknown
        for unknown in context.unresolved_unknowns
        if unknown.requirement_ref == req.requirement_id
    ] == []


# --------------------------------------------------------------------------
# A060 / A053: coverage modes and explicit satisfaction.
# --------------------------------------------------------------------------


def test_minimum_coverage_stops_at_the_declared_minimum() -> None:
    req = requirement(coverage_mode=CoverageMode.MINIMUM, min_items=1, max_items=8)
    context = compile_context(
        ContextSnapshot(
            repository_state=[
                fact("f1", fact_type="owner"),
                fact("f2", fact_type="language"),
                fact("f3", fact_type="size"),
            ]
        ),
        [req],
    )
    assert len(context.repository_state) == 1


def test_all_eligible_coverage_takes_every_eligible_key() -> None:
    req = requirement(coverage_mode=CoverageMode.ALL_ELIGIBLE, min_items=1, max_items=8)
    context = compile_context(
        ContextSnapshot(
            repository_state=[
                fact("f1", fact_type="owner"),
                fact("f2", fact_type="language"),
                fact("f3", fact_type="size"),
            ]
        ),
        [req],
    )
    assert len(context.repository_state) == 3


def test_semantic_keys_coverage_demands_each_declared_key() -> None:
    req = requirement(
        coverage_mode=CoverageMode.SEMANTIC_KEYS,
        required_semantic_keys=["l9:src/a.py:owner", "l9:src/a.py:language"],
        min_items=2,
        max_items=8,
    )
    satisfied = compile_context(
        ContextSnapshot(
            repository_state=[
                fact("f1", fact_type="owner"),
                fact("f2", fact_type="language"),
                fact("f3", fact_type="size"),
            ]
        ),
        [req],
    )
    # Only the declared keys are admitted; the third is not padding.
    assert {item.fact_type for item in satisfied.repository_state} == {"owner", "language"}
    assert satisfied.unresolved_unknowns == []

    missing = compile_context(
        ContextSnapshot(repository_state=[fact("f1", fact_type="owner")]), [req]
    )
    unknowns = [
        unknown
        for unknown in missing.unresolved_unknowns
        if unknown.requirement_ref == req.requirement_id
    ]
    assert unknowns[0].details["missing_semantic_keys"] == ["l9:src/a.py:language"]


def test_satisfaction_needs_the_declared_minimum_not_mere_exhaustion() -> None:
    req = requirement(coverage_mode=CoverageMode.MINIMUM, min_items=2, max_items=8)
    context = compile_context(
        ContextSnapshot(repository_state=[fact("f1", fact_type="owner")]), [req]
    )
    assert len(context.repository_state) == 1
    assert UnknownReasonCode.MISSING_REQUIRED_CONTEXT.value in unknown_codes(context)


# --------------------------------------------------------------------------
# A024 / A064: canonical budget measurement and the global budget.
# --------------------------------------------------------------------------


def test_per_requirement_byte_budget_routes_overflow_through_missing_policy() -> None:
    items = [fact("f1", fact_type="owner"), fact("f2", fact_type="language")]
    # Room for exactly one item, whichever the canonical order picks first.
    tight = max(canonical_cost(item) for item in items) + 1
    req = requirement(
        coverage_mode=CoverageMode.ALL_ELIGIBLE, min_items=1, max_items=8, max_bytes=tight
    )
    context = compile_context(ContextSnapshot(repository_state=items), [req])
    assert len(context.repository_state) == 1
    assert UnknownReasonCode.BUDGET_INSUFFICIENT.value in unknown_codes(context)


def test_global_budget_bounds_the_union_of_selected_items() -> None:
    items = [fact(f"f{i}", fact_type=f"kind{i}") for i in range(4)]
    req = requirement(coverage_mode=CoverageMode.ALL_ELIGIBLE, min_items=1, max_items=8)
    context = compile_context(
        ContextSnapshot(repository_state=items),
        [req],
        budget=ContextBudget(max_total_items=2, max_total_bytes=262_144),
    )
    assert len(context.repository_state) == 2
    assert UnknownReasonCode.BUDGET_INSUFFICIENT.value in unknown_codes(context)


def test_a_block_requirement_that_cannot_fit_blocks_the_compile() -> None:
    items = [fact("f1", fact_type="owner"), fact("f2", fact_type="language")]
    req = requirement(
        coverage_mode=CoverageMode.ALL_ELIGIBLE,
        min_items=1,
        max_items=8,
        max_bytes=max(canonical_cost(item) for item in items) + 1,
        missing_policy=MissingPolicy.BLOCK,
    )
    with pytest.raises(InvalidValueError, match="BLOCK missing policy"):
        compile_context(ContextSnapshot(repository_state=items), [req])


def test_a_reused_item_costs_the_global_budget_once() -> None:
    left = requirement(reason="first", priority=10)
    right = requirement(reason="second", priority=20)
    context = compile_context(
        ContextSnapshot(repository_state=[fact("f1")]),
        [left, right],
        budget=ContextBudget(max_total_items=1, max_total_bytes=262_144),
    )
    assert len(context.repository_state) == 1
    assert UnknownReasonCode.BUDGET_INSUFFICIENT.value not in unknown_codes(context)


# --------------------------------------------------------------------------
# A026-A029: capability and authority.
# --------------------------------------------------------------------------


def capability(item_id: str, capability_id: str, state: str) -> CapabilityFact:
    return CapabilityFact(
        item_id=item_id,
        semantic_key=capability_id,
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=src(item_id),
        scope_mode=ContextScopeMode.GLOBAL,
        capability_id=capability_id,
        state=state,  # type: ignore[arg-type]
    )


def authority(
    item_id: str, authority_id: str, state: str, precedence: int | None = None
) -> AuthorityFact:
    return AuthorityFact(
        item_id=item_id,
        semantic_key=f"{authority_id}::",
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=src(item_id),
        scope_mode=ContextScopeMode.GLOBAL,
        authority_id=authority_id,
        state=state,  # type: ignore[arg-type]
        precedence=precedence,
    )


def _capability_requirement() -> ContextRequirement:
    return requirement(
        context_kind=ContextKind.CAPABILITY_FACT,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
        priority=80,
    )


def _authority_requirement() -> ContextRequirement:
    return requirement(
        context_kind=ContextKind.AUTHORITY_FACT,
        scope_mode=ContextScopeMode.GLOBAL,
        scope_refs=[],
        required=False,
        min_items=0,
        missing_policy=MissingPolicy.OPTIONAL,
        priority=70,
    )


def test_capability_states_stay_distinct_and_required_is_compiler_derived() -> None:
    context = compile_context(
        ContextSnapshot(
            capability_facts=[
                capability("c1", "workspace_mutation", "available"),
                capability("c2", "network_egress", "unavailable"),
                capability("c3", "gpu", "unknown"),
            ]
        ),
        [_capability_requirement()],
    )
    assert [item.capability_id for item in context.capabilities.available] == ["workspace_mutation"]
    assert [item.capability_id for item in context.capabilities.unavailable] == ["network_egress"]
    assert [item.capability_id for item in context.capabilities.unknown] == ["gpu"]
    # Required is derived from the mission, not read from the snapshot.
    assert "workspace_mutation" in {req.capability_id for req in context.capabilities.required}


def test_required_capability_is_never_promoted_to_available() -> None:
    context = compile_context(ContextSnapshot.empty(), [_capability_requirement()])
    assert context.capabilities.required
    assert context.capabilities.available == []


def test_a_required_capability_proven_unavailable_becomes_a_material_unknown() -> None:
    context = compile_context(
        ContextSnapshot(capability_facts=[capability("c1", "workspace_mutation", "unavailable")]),
        [_capability_requirement()],
    )
    assert UnknownReasonCode.UNSUPPORTED_CAPABILITY.value in unknown_codes(context)


def test_authority_states_stay_distinct() -> None:
    context = compile_context(
        ContextSnapshot(
            authority_facts=[
                authority("a1", "repository_write", "granted"),
                authority("a2", "production_deploy", "limit"),
                authority("a3", "secret_read", "unknown"),
            ]
        ),
        [_authority_requirement()],
    )
    assert [item.authority_id for item in context.authority.granted] == ["repository_write"]
    assert [item.authority_id for item in context.authority.limits] == ["production_deploy"]
    assert [item.authority_id for item in context.authority.unknown] == ["secret_read"]


def test_missing_authority_is_never_invented_as_a_grant() -> None:
    context = compile_context(
        ContextSnapshot(authority_facts=[authority("a1", "unrelated_authority", "granted")]),
        [_authority_requirement()],
    )
    granted = {item.authority_id for item in context.authority.granted}
    assert "repository_write" not in granted
    assert UnknownReasonCode.MISSING_AUTHORITY.value in unknown_codes(context)


def test_effective_authority_order_labels_the_compiler_default() -> None:
    context = compile_context(
        ContextSnapshot.empty(),
        [requirement(required=False, min_items=0, missing_policy=MissingPolicy.OPTIONAL)],
    )
    assert context.authority.effective_order == list(AUTHORITY_ORDER)
    assert context.authority.effective_order_source is (
        EffectiveAuthorityOrderSource.COMPILER_DEFAULT
    )


def test_governed_precedence_supersedes_the_compiler_default_order() -> None:
    context = compile_context(
        ContextSnapshot(
            authority_facts=[
                authority("a1", "governed_law", "granted", precedence=0),
                authority("a2", "operator_instruction", "granted", precedence=1),
            ]
        ),
        [_authority_requirement()],
    )
    assert context.authority.effective_order == ["governed_law", "operator_instruction"]
    assert context.authority.effective_order_source is (
        EffectiveAuthorityOrderSource.GOVERNED_CONTEXT
    )


def test_a_caller_hint_cannot_define_the_authority_order() -> None:
    context = compile_context(
        ContextSnapshot.empty(),
        [requirement(required=False, min_items=0, missing_policy=MissingPolicy.OPTIONAL)],
        hints={
            "target_refs": ["src/a.py"],
            "authority_order": ["whatever the caller says"],
            "effective_order": ["whatever the caller says"],
        },
    )
    assert "whatever the caller says" not in context.authority.effective_order
    assert context.authority.effective_order_source is (
        EffectiveAuthorityOrderSource.COMPILER_DEFAULT
    )


# --------------------------------------------------------------------------
# A034 / A035 / A052: digest determinism, materiality, and checkout safety.
# --------------------------------------------------------------------------


def test_identical_inputs_produce_identical_context_digests() -> None:
    req = requirement()
    snapshot = ContextSnapshot(repository_state=[fact("f1")])
    assert compile_context(snapshot, [req]).sha256() == compile_context(snapshot, [req]).sha256()


def test_material_selected_context_change_changes_the_digest() -> None:
    req = requirement()
    before = compile_context(ContextSnapshot(repository_state=[fact("f1", value="team-a")]), [req])
    after = compile_context(ContextSnapshot(repository_state=[fact("f1", value="team-b")]), [req])
    assert before.sha256() != after.sha256()


def test_compiler_identity_is_explicit_and_carries_no_ambient_git_state() -> None:
    context = compile_context(ContextSnapshot(repository_state=[fact("f1")]), [requirement()])
    identity = context.provenance.compiler_identity
    assert identity.package_version == "0.1.0"
    assert identity.semantics_version
    payload = context.to_canonical_dict()
    for forbidden in ("git", "HEAD", "branch", "hostname"):
        assert forbidden not in str(payload.get("provenance"))


def test_provenance_records_selected_item_digests_not_a_snapshot_digest() -> None:
    snapshot = ContextSnapshot(
        repository_state=[
            fact("f1"),
            fact("f9", subject="docs/x.md", scope_refs=("docs/x.md",)),
        ]
    )
    context = compile_context(snapshot, [requirement()])
    assert set(context.provenance.selected_item_digests) == {"f1"}
    assert snapshot.audit_digest() not in str(context.provenance.to_canonical_dict())


# --------------------------------------------------------------------------
# Discovery projection (A016 / A063).
# --------------------------------------------------------------------------


def test_discovery_records_governed_signals_with_provenance() -> None:
    constraint = GovernedConstraint(
        item_id="g1",
        semantic_key="external_side_effect",
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=src("g1"),
        scope_mode=ContextScopeMode.GLOBAL,
        constraint_id="external_side_effect",
        statement="proven by review",
    )
    snapshot = ContextSnapshot(architecture_constraints=[constraint])
    intent = intent_for("Update the payment module owner record.", target_refs=["src/a.py"])
    scope = TaskScopeCompiler().compile(intent)
    discovery = ContextDiscoveryCompiler().compile(scope, snapshot, resolve_snapshot(snapshot))
    assert discovery.architecture_signal_refs == ["external_side_effect"]
    assert discovery.selected_item_digests["g1"] == constraint.candidate_digest()


def test_discovery_ignores_memory_and_ungoverned_material() -> None:
    entity = EntityContext(
        item_id="e1",
        semantic_key="module:payments",
        authority_level=AuthorityLevel.UNVERIFIED,
        source_ref=src("e1", coordinate=None),
        scope_mode=ContextScopeMode.GLOBAL,
        entity_id="payments",
        entity_type="module",
        relation_to_task="subject",
    )
    snapshot = ContextSnapshot(relevant_entities=[entity], memory_context=[memory("m1", "mem")])
    intent = intent_for("Update the payment module owner record.", target_refs=["src/a.py"])
    scope = TaskScopeCompiler().compile(intent)
    discovery = ContextDiscoveryCompiler().compile(scope, snapshot, resolve_snapshot(snapshot))
    assert discovery.routing_fact_refs == []


# --------------------------------------------------------------------------
# A057: requirement planning never depends on downstream obligations.
# --------------------------------------------------------------------------


def test_requirement_planning_is_stable_under_route_and_kernel_inputs_only() -> None:
    intent = intent_for("Update the payment module owner record.", target_refs=["src/a.py"])
    scope = TaskScopeCompiler().compile(intent)
    snapshot = ContextSnapshot.empty()
    discovery = ContextDiscoveryCompiler().compile(scope, snapshot, resolve_snapshot(snapshot))
    plan = ContextRequirementPlanner().plan(intent, scope, discovery, activation_plan(), KERNELS)
    again = ContextRequirementPlanner().plan(intent, scope, discovery, activation_plan(), KERNELS)
    assert plan.plan_id == again.plan_id
    # Naming a target reference is what makes repository context required.
    repository = [
        req for req in plan.requirements if req.context_kind is ContextKind.REPOSITORY_STATE
    ][0]
    assert repository.required is True
    assert repository.missing_policy is MissingPolicy.PRESERVE_UNKNOWN


def test_a_legacy_task_gains_no_blocking_external_requirement() -> None:
    intent = intent_for("Review the pack.")
    scope = TaskScopeCompiler().compile(intent)
    snapshot = ContextSnapshot.empty()
    discovery = ContextDiscoveryCompiler().compile(scope, snapshot, resolve_snapshot(snapshot))
    plan = ContextRequirementPlanner().plan(intent, scope, discovery, activation_plan(), KERNELS)
    assert all(req.required is False for req in plan.requirements)
    assert all(req.missing_policy is MissingPolicy.OPTIONAL for req in plan.requirements)


# --------------------------------------------------------------------------
# A031: closure is fail-closed on a tampered context.
# --------------------------------------------------------------------------


def test_closure_rejects_a_selected_item_without_a_relevance_binding() -> None:
    # Optional so the disposition check passes and the binding check is the
    # one that has to catch the tampering.
    req = requirement(required=False, min_items=0, missing_policy=MissingPolicy.OPTIONAL)
    context = compile_context(ContextSnapshot(repository_state=[fact("f1")]), [req])
    stripped = context.model_copy(
        update={
            "repository_state": [
                context.repository_state[0].model_copy(update={"selected_because": []})
            ]
        }
    )
    plan = ContextRequirementPlan(
        task_scope_digest=context.provenance.task_scope_digest,
        matched_route="pack_review",
        global_budget=ContextBudget(max_total_items=64, max_total_bytes=262_144),
        requirements=[req],
    )
    with pytest.raises(InvalidValueError, match="every_selected_item_has_relevance_binding"):
        ContextClosureValidator().validate(
            context=stripped, requirement_plan=plan, resolutions={}, kernels=KERNELS
        )


def test_closure_rejects_a_context_whose_kernels_diverge_from_the_bindings() -> None:
    req = requirement(required=False, min_items=0, missing_policy=MissingPolicy.OPTIONAL)
    context = compile_context(ContextSnapshot.empty(), [req])
    tampered = context.model_copy(update={"selected_kernels": []})
    plan = ContextRequirementPlan(
        task_scope_digest=context.provenance.task_scope_digest,
        matched_route="pack_review",
        global_budget=ContextBudget(max_total_items=64, max_total_bytes=262_144),
        requirements=[req],
    )
    with pytest.raises(
        InvalidValueError, match="every_selected_kernel_equals_downstream_kernel_binding"
    ):
        ContextClosureValidator().validate(
            context=tampered, requirement_plan=plan, resolutions={}, kernels=KERNELS
        )
