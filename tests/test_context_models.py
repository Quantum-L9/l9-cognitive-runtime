"""Context IR model law: identity, scope, bounds, and the machine schema.

These cover the properties a compiled context depends on before any selection
happens — if identity is caller-chosen, if an exclusion is decorative, or if the
snapshot is unbounded on input, everything downstream inherits the defect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from l9_cognitive_runtime.compiler.task_context import preflight_snapshot
from l9_cognitive_runtime.compiler.task_scope import TaskScopeCompiler, scope_reference_set
from l9_cognitive_runtime.models.context import (
    SNAPSHOT_MAX_BYTES,
    SNAPSHOT_MAX_ITEMS,
    ApplicableLaw,
    AuthorityFact,
    AuthorityLevel,
    CompiledTaskContext,
    ContextKind,
    ContextRequirement,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    ContextUnknown,
    CoverageMode,
    EntityContext,
    FreshnessRequirement,
    GovernedConstraint,
    MemoryContext,
    MissingPolicy,
    RepositoryState,
    UnknownMateriality,
    UnknownReasonCode,
    derive_id,
)
from l9_cognitive_runtime.models.errors import ModelValidationError
from tests.conftest import intent_for

ROOT = Path(__file__).resolve().parents[1]

# Direct model construction raises pydantic's own error; ``from_mapping`` — the
# path every host surface uses — translates it into the repository's typed
# ``ModelValidationError``. Both are the same fail-closed refusal.
FAIL_CLOSED = (ValidationError, ModelValidationError)


def source(source_id: str = "src", coordinate: str | None = "rev-1") -> ContextSourceRef:
    return ContextSourceRef(
        source_id=source_id,
        source_kind="repository",
        locator=f"repo://{source_id}",
        immutable_coordinate=coordinate,
    )


def entity(entity_id: str, *, relation: str = "target") -> EntityContext:
    return EntityContext(
        semantic_key=f"module:{entity_id}",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source(entity_id),
        scope_mode=ContextScopeMode.GLOBAL,
        entity_id=entity_id,
        entity_type="module",
        relation_to_task=relation,
    )


# ---------------------------------------------------------------------------
# INV-CTX-011: item identity is compiler-owned, not caller-chosen.
# ---------------------------------------------------------------------------


def test_item_id_is_derived_when_omitted() -> None:
    item = entity("payments")
    assert item.item_id.startswith("ctxitem.sha256:")
    assert len(item.item_id.split(":")[1]) == 64


def test_identical_source_and_claim_produce_identical_item_id() -> None:
    """Two independent constructions of the same candidate agree, across runs."""
    first = entity("payments")
    second = entity("payments")
    assert first.item_id == second.item_id
    assert first.item_id == first.expected_item_id()


def test_a_supplied_item_id_must_equal_the_canonical_recipe() -> None:
    item = entity("payments")
    same = EntityContext(
        item_id=item.item_id,
        semantic_key="module:payments",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source("payments"),
        scope_mode=ContextScopeMode.GLOBAL,
        entity_id="payments",
        entity_type="module",
        relation_to_task="target",
    )
    # Not a comparison with what was passed in — the accepted value must equal
    # the recipe recomputed from the finished item.
    assert same.item_id == same.expected_item_id()
    assert same.candidate_digest() == item.candidate_digest()


@pytest.mark.parametrize(
    "fake",
    [
        "entity.payments",
        "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
        "ctxitem.sha256:" + "0" * 64,
    ],
)
def test_a_caller_chosen_item_id_cannot_change_semantic_identity(fake: str) -> None:
    """A different supplied id must not produce a different, accepted item."""
    with pytest.raises(FAIL_CLOSED, match="canonical ctxitem recipe"):
        EntityContext(
            item_id=fake,
            semantic_key="module:payments",
            authority_level=AuthorityLevel.GOVERNED_VERIFIED,
            source_ref=source("payments"),
            scope_mode=ContextScopeMode.GLOBAL,
            entity_id="payments",
            entity_type="module",
            relation_to_task="target",
        )


def test_item_id_binds_the_claim() -> None:
    assert entity("payments", relation="target").item_id != (
        entity("payments", relation="dependency").item_id
    )


def test_item_id_binds_the_immutable_source_coordinate() -> None:
    a = EntityContext(
        semantic_key="module:payments",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source("payments", coordinate="rev-1"),
        scope_mode=ContextScopeMode.GLOBAL,
        entity_id="payments",
        entity_type="module",
        relation_to_task="target",
    )
    b = EntityContext(
        semantic_key="module:payments",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source("payments", coordinate="rev-2"),
        scope_mode=ContextScopeMode.GLOBAL,
        entity_id="payments",
        entity_type="module",
        relation_to_task="target",
    )
    assert a.item_id != b.item_id


def test_semantic_key_must_match_the_kind_recipe() -> None:
    with pytest.raises(FAIL_CLOSED, match="recipe"):
        EntityContext(
            semantic_key="whatever-the-caller-wants",
            authority_level=AuthorityLevel.GOVERNED_VERIFIED,
            source_ref=source("payments"),
            scope_mode=ContextScopeMode.GLOBAL,
            entity_id="payments",
            entity_type="module",
            relation_to_task="target",
        )


def test_governed_item_requires_immutable_provenance() -> None:
    with pytest.raises(FAIL_CLOSED, match="immutable_coordinate"):
        EntityContext(
            semantic_key="module:payments",
            authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
            source_ref=source("payments", coordinate=None),
            scope_mode=ContextScopeMode.GLOBAL,
            entity_id="payments",
            entity_type="module",
            relation_to_task="target",
        )


def test_memory_authority_is_ceilinged_at_informative() -> None:
    with pytest.raises(FAIL_CLOSED, match="ceilinged"):
        MemoryContext(
            semantic_key="mem-1",
            authority_level=AuthorityLevel.GOVERNED_VERIFIED,
            source_ref=source("mem"),
            scope_mode=ContextScopeMode.GLOBAL,
            memory_id="mem-1",
            memory_kind="recall",
        )


def test_snapshot_candidate_cannot_supply_selection_lineage() -> None:
    with pytest.raises(FAIL_CLOSED, match="selected_because"):
        ContextSnapshot(
            relevant_entities=[
                EntityContext(
                    semantic_key="module:payments",
                    authority_level=AuthorityLevel.GOVERNED_VERIFIED,
                    source_ref=source("payments"),
                    scope_mode=ContextScopeMode.GLOBAL,
                    entity_id="payments",
                    entity_type="module",
                    relation_to_task="target",
                    selected_because=["ctxreq.sha256:" + "0" * 64],
                )
            ]
        )


def test_unknown_identity_is_deterministic_and_prose_free() -> None:
    first = ContextUnknown(
        reason_code=UnknownReasonCode.MISSING_AUTHORITY,
        materiality=UnknownMateriality.NON_BLOCKING,
        details={"authority_id": "repository_write", "state": "absent"},
    )
    second = ContextUnknown(
        reason_code=UnknownReasonCode.MISSING_AUTHORITY,
        materiality=UnknownMateriality.NON_BLOCKING,
        details={"state": "absent", "authority_id": "repository_write"},
    )
    assert first.unknown_id == second.unknown_id == first.expected_unknown_id()


def test_unknown_id_must_equal_the_recipe() -> None:
    with pytest.raises(FAIL_CLOSED, match="ctxunk recipe"):
        ContextUnknown(
            unknown_id=derive_id("ctxunk", {"nonsense": True}),
            reason_code=UnknownReasonCode.MISSING_AUTHORITY,
            materiality=UnknownMateriality.NON_BLOCKING,
        )


# ---------------------------------------------------------------------------
# INV-CTX-006: scope exclusion is real.
# ---------------------------------------------------------------------------


def test_excluded_reference_leaves_the_eligible_scope_set() -> None:
    scope = TaskScopeCompiler().compile(
        intent_for(
            "Update the billing module.",
            target_refs=["src/billing", "src/billing/legacy"],
            excluded_refs=["src/billing/legacy"],
        )
    )
    assert scope_reference_set(scope) == frozenset({"src/billing"})
    assert "src/billing/legacy" in scope.excluded_refs


def test_include_exclude_conflict_is_a_blocking_unknown_not_a_silent_include() -> None:
    scope = TaskScopeCompiler().compile(
        intent_for(
            "Update the billing module.",
            target_refs=["src/billing"],
            excluded_refs=["src/billing"],
        )
    )
    assert scope.scope_conflicts == ("src/billing",)
    # The reference is in neither the eligible set nor silently included.
    assert "src/billing" not in scope_reference_set(scope)
    blocking = [
        unknown
        for unknown in scope.unresolved_unknowns
        if unknown.reason_code is UnknownReasonCode.AMBIGUOUS_SCOPE
        and unknown.materiality is UnknownMateriality.BLOCKING
    ]
    assert blocking, scope.unresolved_unknowns
    assert blocking[0].details["conflicting_refs"] == ["src/billing"]


def test_exclusion_matching_is_exact_and_invents_no_path_semantics() -> None:
    """A prefix is not an ancestor: only exact references are excluded."""
    scope = TaskScopeCompiler().compile(
        intent_for(
            "Update the billing module.",
            target_refs=["src/billing/api.py"],
            excluded_refs=["src/billing"],
        )
    )
    assert scope_reference_set(scope) == frozenset({"src/billing/api.py"})
    assert scope.scope_conflicts == ()


def test_only_declared_scope_hint_keys_reach_the_task_scope() -> None:
    scope = TaskScopeCompiler().compile(
        intent_for(
            "Update the billing module.",
            target_refs=["src/billing"],
            extra={"context_signals": ["multiple_workers"], "repository_state": ["anything"]},
        )
    )
    canonical = scope.to_canonical_dict()
    assert "multiple_workers" not in json.dumps(canonical)
    assert scope.target_refs == ["src/billing"]


# ---------------------------------------------------------------------------
# INV-CTX-007: the snapshot is bounded on input.
# ---------------------------------------------------------------------------


def _entities(count: int) -> ContextSnapshot:
    return ContextSnapshot(relevant_entities=[entity(f"m{index:04d}") for index in range(count)])


def test_a_boundary_sized_snapshot_is_accepted() -> None:
    snapshot = _entities(SNAPSHOT_MAX_ITEMS)
    assert snapshot.item_count() == SNAPSHOT_MAX_ITEMS
    preflight_snapshot(snapshot)


def test_one_item_over_the_ceiling_is_rejected() -> None:
    snapshot = _entities(SNAPSHOT_MAX_ITEMS + 1)
    with pytest.raises(FAIL_CLOSED, match="maximum item count"):
        preflight_snapshot(snapshot)


def test_one_byte_over_the_ceiling_is_rejected() -> None:
    """Few items, far too many bytes: the byte ceiling is independent."""
    padded = RepositoryState(
        semantic_key="repo:src/big:content",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source("big"),
        scope_mode=ContextScopeMode.GLOBAL,
        repository_id="repo",
        revision="rev-1",
        subject_ref="src/big",
        fact_type="content",
        value="x" * (SNAPSHOT_MAX_BYTES + 1),
    )
    snapshot = ContextSnapshot(repository_state=[padded])
    assert snapshot.item_count() == 1
    assert snapshot.canonical_byte_size() > SNAPSHOT_MAX_BYTES
    with pytest.raises(FAIL_CLOSED, match="maximum canonical byte size"):
        preflight_snapshot(snapshot)


def test_oversized_input_is_never_silently_truncated() -> None:
    snapshot = _entities(SNAPSHOT_MAX_ITEMS + 5)
    with pytest.raises(ModelValidationError):
        preflight_snapshot(snapshot)
    # The rejected snapshot is untouched: nothing was dropped to make it fit.
    assert snapshot.item_count() == SNAPSHOT_MAX_ITEMS + 5


# ---------------------------------------------------------------------------
# INV-CTX-008 / INV-CTX-026: requirement shape is mechanically decidable.
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
        "max_bytes": 1024,
        "missing_policy": MissingPolicy.OPTIONAL,
    }
    payload.update(overrides)
    return ContextRequirement(**payload)


def test_every_requirement_needs_a_finite_bound() -> None:
    with pytest.raises(FAIL_CLOSED, match="max_items or max_bytes"):
        _requirement(max_items=None, max_bytes=None)


def test_max_items_may_not_be_below_min_items() -> None:
    with pytest.raises(FAIL_CLOSED, match="at least min_items"):
        _requirement(required=True, min_items=4, max_items=2, missing_policy=MissingPolicy.BLOCK)


def test_required_requirement_cannot_be_optional() -> None:
    with pytest.raises(FAIL_CLOSED, match="OPTIONAL missing policy"):
        _requirement(required=True, min_items=1, missing_policy=MissingPolicy.OPTIONAL)


def test_semantic_keys_coverage_requires_keys() -> None:
    with pytest.raises(FAIL_CLOSED, match="required_semantic_keys"):
        _requirement(coverage_mode=CoverageMode.SEMANTIC_KEYS)


def test_scoped_requirement_requires_scope_refs() -> None:
    with pytest.raises(FAIL_CLOSED, match="scoped requirement"):
        _requirement(scope_mode=ContextScopeMode.SCOPED, scope_refs=[])


def test_requirement_identity_is_deterministic() -> None:
    first = _requirement()
    second = _requirement()
    assert first.requirement_id == second.requirement_id
    assert first.requirement_id.startswith("ctxreq.sha256:")


# ---------------------------------------------------------------------------
# The machine schema ships and matches the model that produces the artifact.
# ---------------------------------------------------------------------------

SCHEMA_PATH = ROOT / "contracts" / "compiled_task_context.schema.json"


def test_the_compiled_context_schema_ships_with_the_contracts() -> None:
    assert SCHEMA_PATH.is_file()


def test_the_schema_has_not_drifted_from_the_model() -> None:
    """Regenerate with ``CompiledTaskContext.model_json_schema(mode="serialization")``."""
    shipped = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    generated = CompiledTaskContext.model_json_schema(mode="serialization")
    for key, value in generated.items():
        assert shipped[key] == value, key


def test_a_real_compiled_context_validates_against_the_shipped_schema(
    valid_pack: Path,
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(bundle.task_context.to_canonical_dict(), schema)


def test_law_and_authority_facts_round_trip_through_the_snapshot() -> None:
    snapshot = ContextSnapshot(
        applicable_law=[
            ApplicableLaw(
                semantic_key="LAW_A",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("law-a"),
                scope_mode=ContextScopeMode.GLOBAL,
                law_id="LAW_A",
                statement="a",
            )
        ],
        authority_facts=[
            AuthorityFact(
                semantic_key="repository_write::",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("auth"),
                scope_mode=ContextScopeMode.GLOBAL,
                authority_id="repository_write",
                state="granted",
            )
        ],
        architecture_constraints=[
            GovernedConstraint(
                semantic_key="multiple_workers",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("arch"),
                scope_mode=ContextScopeMode.GLOBAL,
                constraint_id="multiple_workers",
                statement="proven",
            )
        ],
    )
    rebuilt = ContextSnapshot.from_mapping(snapshot.to_canonical_dict())
    assert rebuilt.sha256() == snapshot.sha256()
