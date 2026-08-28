"""Canonical context model law (A006, A013-A015, A032, A033, A055-A056, A061-A062).

These tests pin the properties the compiler relies on being structurally
impossible to violate: no self-digest, kind-defined semantic keys, governed
provenance, compiler-owned selection lineage, and deterministic identity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.models.context import (
    CONTEXT_COMPILER_SEMANTICS_VERSION,
    ApplicableLaw,
    AuthorityContext,
    AuthorityFact,
    AuthorityLevel,
    AuthorityRequirement,
    CapabilityContext,
    CapabilityFact,
    CapabilityRequirement,
    CompiledTaskContext,
    CompilerIdentity,
    ContextBudget,
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
    EffectiveAuthorityOrderSource,
    EntityContext,
    FreshnessRequirement,
    GovernedConstraint,
    MemoryContext,
    MissingPolicy,
    PriorDecision,
    RepositoryState,
    TaskScope,
    UnknownMateriality,
    UnknownReasonCode,
    canonical_cost,
)
from l9_cognitive_runtime.models.errors import ModelValidationError, UnknownFieldError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "compiled_task_context.schema.json"


def source(coordinate: str | None = "rev-1", digest: str | None = None) -> ContextSourceRef:
    return ContextSourceRef(
        source_id="src.governance",
        source_kind="repository",
        locator="repo://l9/main",
        immutable_coordinate=coordinate,
        content_digest=digest,
    )


def repository_mapping(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "item_id": "repo.fact.1",
        "semantic_key": "l9:src/a.py:exists",
        "authority_level": "governed_authoritative",
        "source_ref": source().to_canonical_dict(),
        "scope_mode": "scoped",
        "scope_refs": ["src/a.py"],
        "repository_id": "l9",
        "revision": "rev-1",
        "subject_ref": "src/a.py",
        "fact_type": "exists",
        "value": True,
    }
    data.update(overrides)
    return data


def repository_fact(**overrides: Any) -> RepositoryState:
    """Build a governed repository fact through the fail-closed boundary."""
    return RepositoryState.from_mapping(repository_mapping(**overrides))


# --------------------------------------------------------------------------
# A055 / A056: semantic keys are kind-defined; repository state is one claim.
# --------------------------------------------------------------------------


def test_kind_recipe_defines_the_semantic_key() -> None:
    fact = repository_fact()
    assert fact.semantic_key == "l9:src/a.py:exists"
    assert fact.expected_semantic_key() == fact.semantic_key


def test_caller_chosen_semantic_key_that_disagrees_with_the_recipe_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="semantic_key must equal"):
        repository_fact(semantic_key="whatever-the-caller-likes")


def test_every_kind_declares_its_own_recipe() -> None:
    entity = EntityContext(
        item_id="e1",
        semantic_key="module:payments",
        authority_level=AuthorityLevel.INFORMATIVE,
        source_ref=source(),
        scope_mode=ContextScopeMode.GLOBAL,
        entity_id="payments",
        entity_type="module",
        relation_to_task="subject",
    )
    authority = AuthorityFact(
        item_id="a1",
        semantic_key="repository_write::src/a.py,src/b.py",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source(),
        scope_mode=ContextScopeMode.GLOBAL,
        authority_id="repository_write",
        state="granted",
        action_scope=["src/b.py", "src/a.py"],
    )
    assert entity.semantic_key == "module:payments"
    # Action scope is canonicalized before it reaches the key, so caller order
    # cannot change identity.
    assert authority.action_scope == ["src/a.py", "src/b.py"]


def test_repository_state_rejects_an_opaque_multi_fact_bag() -> None:
    with pytest.raises(UnknownFieldError):
        RepositoryState.from_mapping(repository_mapping(facts={"a": 1, "b": 2}))


def test_repository_state_requires_a_revision() -> None:
    with pytest.raises(ModelValidationError):
        repository_fact(revision="")


# --------------------------------------------------------------------------
# A015 / A013: governed provenance and compiler-owned selection lineage.
# --------------------------------------------------------------------------


def test_governed_item_without_immutable_provenance_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="immutable_coordinate or content_digest"):
        repository_fact(source_ref=source(coordinate=None).to_canonical_dict())


def test_governed_item_may_prove_provenance_with_a_content_digest_instead() -> None:
    fact = repository_fact(source_ref=source(coordinate=None, digest="a" * 64).to_canonical_dict())
    assert fact.source_ref.has_immutable_provenance


def _memory_mapping(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "item_id": "m1",
        "semantic_key": "mem-1",
        "authority_level": "informative",
        "source_ref": source(coordinate=None).to_canonical_dict(),
        "scope_mode": "global",
        "memory_id": "mem-1",
        "memory_kind": "recall",
    }
    data.update(overrides)
    return data


def test_informative_item_needs_no_immutable_coordinate() -> None:
    memory = MemoryContext.from_mapping(_memory_mapping())
    assert memory.authority_level is AuthorityLevel.INFORMATIVE


def test_memory_authority_is_ceilinged_at_informative() -> None:
    with pytest.raises(ModelValidationError, match="ceilinged at informative"):
        MemoryContext.from_mapping(
            _memory_mapping(
                authority_level="governed_authoritative",
                source_ref=source().to_canonical_dict(),
            )
        )


def test_snapshot_candidate_may_not_supply_selection_lineage() -> None:
    with pytest.raises(ModelValidationError, match="must not supply selected_because"):
        ContextSnapshot.from_mapping(
            {"repository_state": [repository_mapping(selected_because=["ctxreq.sha256:x"])]}
        )


# --------------------------------------------------------------------------
# A054: scope mode is explicit; no implicit empty-list semantics.
# --------------------------------------------------------------------------


def test_scoped_item_requires_scope_refs_and_global_item_forbids_them() -> None:
    with pytest.raises(ModelValidationError, match="scoped context item requires"):
        repository_fact(scope_mode="scoped", scope_refs=[])
    with pytest.raises(ModelValidationError, match="global context item requires empty"):
        repository_fact(scope_mode="global", scope_refs=["src/a.py"])


# --------------------------------------------------------------------------
# A061 / A062: deterministic full-digest identity, stable unknown reason codes.
# --------------------------------------------------------------------------


def test_compiler_derived_ids_are_full_sha256_recipes() -> None:
    scope = TaskScope(mission="do the thing", task_type="t")
    assert scope.scope_id.startswith("scope.sha256:")
    assert len(scope.scope_id.split(":")[1]) == 64


def test_identical_normalized_payloads_produce_identical_ids() -> None:
    left = TaskScope(mission="m", task_type="t", target_refs=["b", "a"])
    right = TaskScope(mission="m", task_type="t", target_refs=["a", "b", "a"])
    assert left.scope_id == right.scope_id
    assert left.sha256() == right.sha256()


def test_unknown_identity_uses_reason_code_and_details_not_prose() -> None:
    left = ContextUnknown(
        requirement_ref="ctxreq.sha256:" + "0" * 64,
        reason_code=UnknownReasonCode.MISSING_REQUIRED_CONTEXT,
        materiality=UnknownMateriality.BLOCKING,
        details={"context_kind": "repository_state"},
    )
    right = ContextUnknown(
        requirement_ref="ctxreq.sha256:" + "0" * 64,
        reason_code=UnknownReasonCode.MISSING_REQUIRED_CONTEXT,
        materiality=UnknownMateriality.NON_BLOCKING,
        details={"context_kind": "repository_state"},
    )
    other = ContextUnknown(
        reason_code=UnknownReasonCode.BUDGET_INSUFFICIENT,
        materiality=UnknownMateriality.BLOCKING,
        details={"context_kind": "repository_state"},
    )
    # Identity is the reason code plus canonical details — materiality is a
    # classification of the same unknown, not a different unknown.
    assert left.unknown_id == right.unknown_id
    assert left.unknown_id != other.unknown_id
    assert left.unknown_id.startswith("ctxunk.sha256:")


def test_a_forged_deterministic_id_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="deterministic scope recipe"):
        TaskScope.from_mapping(
            {"scope_id": "scope.sha256:" + "0" * 64, "mission": "m", "task_type": "t"}
        )


# --------------------------------------------------------------------------
# A060: coverage modes are explicit and mechanically distinguishable.
# --------------------------------------------------------------------------


def _requirement(**overrides: Any) -> ContextRequirement:
    data: dict[str, Any] = {
        "context_kind": ContextKind.REPOSITORY_STATE.value,
        "reason": "because the task names this file",
        "required": True,
        "scope_mode": ContextScopeMode.GLOBAL.value,
        "scope_refs": [],
        "freshness_requirement": FreshnessRequirement.SNAPSHOT_BOUND.value,
        "minimum_authority": AuthorityLevel.GOVERNED_VERIFIED.value,
        "priority": 10,
        "coverage_mode": CoverageMode.MINIMUM.value,
        "min_items": 1,
        "max_items": 4,
        "max_bytes": 4096,
        "missing_policy": MissingPolicy.PRESERVE_UNKNOWN.value,
    }
    data.update(overrides)
    return ContextRequirement.from_mapping(data)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"required": True, "min_items": 0}, "min_items >= 1"),
        ({"required": True, "missing_policy": "OPTIONAL"}, "cannot use the OPTIONAL"),
        ({"max_items": 0}, "max_items must be positive"),
        ({"min_items": 3, "max_items": 2}, "at least min_items"),
        ({"max_items": None, "max_bytes": None}, "at least one of max_items or max_bytes"),
        (
            {"coverage_mode": "minimum", "required_semantic_keys": ["k"]},
            "forbids required_semantic_keys",
        ),
        (
            {"coverage_mode": "semantic_keys", "required_semantic_keys": []},
            "requires required_semantic_keys",
        ),
        (
            {
                "coverage_mode": "semantic_keys",
                "required_semantic_keys": ["a", "b"],
                "min_items": 1,
            },
            "min_items >= number of required keys",
        ),
        (
            {"freshness_requirement": "exact_revision"},
            "requires a coordinate_constraint",
        ),
        ({"scope_mode": "scoped"}, "scoped requirement requires"),
    ],
)
def test_requirement_shape_is_mechanically_decidable(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ModelValidationError, match=message):
        _requirement(**overrides)


def test_optional_requirement_may_use_min_items_zero() -> None:
    requirement = _requirement(required=False, min_items=0, missing_policy="OPTIONAL")
    assert requirement.min_items == 0


def test_requirement_plan_is_canonically_ordered_regardless_of_input_order() -> None:
    low = _requirement(priority=5, reason="first")
    high = _requirement(priority=90, reason="last")
    forward = ContextRequirementPlan(
        task_scope_digest="a" * 64,
        matched_route="r",
        global_budget=ContextBudget(max_total_items=10, max_total_bytes=1024),
        requirements=[low, high],
    )
    reversed_plan = ContextRequirementPlan(
        task_scope_digest="a" * 64,
        matched_route="r",
        global_budget=ContextBudget(max_total_items=10, max_total_bytes=1024),
        requirements=[high, low],
    )
    assert [r.priority for r in forward.requirements] == [5, 90]
    assert forward.plan_id == reversed_plan.plan_id
    assert forward.sha256() == reversed_plan.sha256()


# --------------------------------------------------------------------------
# A006 / A032 / A033: the canonical IR and the acyclic digest.
# --------------------------------------------------------------------------


def empty_context() -> CompiledTaskContext:
    return CompiledTaskContext(
        task_scope=TaskScope(mission="m", task_type="t"),
        capabilities=CapabilityContext(),
        authority=AuthorityContext(
            effective_order=["user task"],
            effective_order_source=EffectiveAuthorityOrderSource.COMPILER_DEFAULT,
        ),
        provenance=ContextProvenance(
            task_scope_digest="a" * 64,
            discovery_digest="b" * 64,
            context_requirements_digest="c" * 64,
            compiler_identity=CompilerIdentity(
                package_version="0.1.0",
                semantics_version=CONTEXT_COMPILER_SEMANTICS_VERSION,
            ),
        ),
    )


def test_compiled_task_context_rejects_unknown_fields() -> None:
    with pytest.raises(ModelValidationError):
        CompiledTaskContext.from_mapping({**empty_context().to_canonical_dict(), "extra_field": 1})


def test_context_provenance_cannot_carry_a_context_digest() -> None:
    payload = empty_context().to_canonical_dict()
    payload["provenance"]["context_digest"] = "d" * 64
    with pytest.raises(ModelValidationError):
        CompiledTaskContext.from_mapping(payload)


def test_context_provenance_cannot_carry_a_whole_snapshot_digest() -> None:
    payload = empty_context().to_canonical_dict()
    payload["provenance"]["whole_context_snapshot_digest"] = "d" * 64
    with pytest.raises(ModelValidationError):
        CompiledTaskContext.from_mapping(payload)


def test_context_digest_computes_without_self_reference() -> None:
    context = empty_context()
    digest = context.sha256()
    assert len(digest) == 64
    assert digest not in json.dumps(context.to_canonical_dict())
    # Recomputation is stable: the digest is not an input to itself.
    assert context.sha256() == digest


def test_compiler_identity_is_explicit_and_non_empty() -> None:
    with pytest.raises(ModelValidationError):
        CompilerIdentity.from_mapping({"package_version": "", "semantics_version": "2.0.0"})


# --------------------------------------------------------------------------
# A058 / A059: snapshot facts cannot declare what the task requires.
# --------------------------------------------------------------------------


def test_capability_fact_cannot_declare_required() -> None:
    with pytest.raises(ModelValidationError):
        CapabilityFact.from_mapping(
            {
                "item_id": "c1",
                "semantic_key": "workspace_mutation",
                "authority_level": "governed_verified",
                "source_ref": source().to_canonical_dict(),
                "scope_mode": "global",
                "capability_id": "workspace_mutation",
                "state": "required",
            }
        )


def test_authority_fact_cannot_declare_required() -> None:
    with pytest.raises(ModelValidationError):
        AuthorityFact.from_mapping(
            {
                "item_id": "a1",
                "semantic_key": "repository_write::",
                "authority_level": "governed_verified",
                "source_ref": source().to_canonical_dict(),
                "scope_mode": "global",
                "authority_id": "repository_write",
                "state": "required",
            }
        )


def test_capability_and_authority_requirements_are_compiler_shaped() -> None:
    capability = CapabilityRequirement(
        capability_id="workspace_mutation", reason="mutation mission", source_refs=["intent:x"]
    )
    authority = AuthorityRequirement(
        authority_id="repository_write", reason="mutation mission", source_refs=["intent:x"]
    )
    assert capability.requirement_id.startswith("capreq.sha256:")
    assert authority.requirement_id.startswith("authreq.sha256:")


# --------------------------------------------------------------------------
# A048: the external schema mirrors the typed model.
# --------------------------------------------------------------------------


def test_schema_matches_the_typed_model_shape() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(CompiledTaskContext.model_fields)
    provenance = schema["$defs"]["context_provenance"]
    assert provenance["additionalProperties"] is False
    assert set(provenance["required"]) == set(ContextProvenance.model_fields)
    forbidden = {entry["required"][0] for entry in provenance["not"]["anyOf"]}
    assert forbidden == {"context_digest", "whole_context_snapshot_digest"}


def test_schema_validates_a_compiled_context_and_rejects_a_context_digest() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = empty_context().to_canonical_dict()
    jsonschema.validate(payload, schema)
    payload["provenance"]["context_digest"] = "d" * 64
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


# --------------------------------------------------------------------------
# Budget measurement is canonical UTF-8 JSON bytes (A024).
# --------------------------------------------------------------------------


def test_candidate_cost_is_canonical_utf8_json_bytes_and_excludes_lineage() -> None:
    fact = repository_fact()
    selected = fact.model_copy(update={"selected_because": ["ctxreq.sha256:" + "0" * 64]})
    assert canonical_cost(fact) == canonical_cost(selected)
    assert canonical_cost(fact) == len(
        json.dumps(
            fact.candidate_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    )


def test_prior_decision_distinguishes_status() -> None:
    statuses = {status.value for status in DecisionStatus}
    assert statuses == {"active", "superseded", "unknown"}
    decision = PriorDecision(
        item_id="d1",
        semantic_key="ADR-1",
        authority_level=AuthorityLevel.GOVERNED_VERIFIED,
        source_ref=source(),
        scope_mode=ContextScopeMode.GLOBAL,
        decision_id="ADR-1",
        status=DecisionStatus.SUPERSEDED,
        statement="old",
    )
    assert decision.status is DecisionStatus.SUPERSEDED


def test_applicable_law_precedence_must_be_non_negative() -> None:
    with pytest.raises(ModelValidationError):
        ApplicableLaw.from_mapping(
            {
                "item_id": "l1",
                "semantic_key": "LAW-1",
                "authority_level": "governed_authoritative",
                "source_ref": source().to_canonical_dict(),
                "scope_mode": "global",
                "law_id": "LAW-1",
                "statement": "s",
                "precedence": -1,
            }
        )


def test_governed_constraint_key_is_the_constraint_id() -> None:
    constraint = GovernedConstraint(
        item_id="g1",
        semantic_key="external_side_effect",
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=source(),
        scope_mode=ContextScopeMode.GLOBAL,
        constraint_id="external_side_effect",
        statement="proven",
    )
    assert constraint.expected_semantic_key() == "external_side_effect"


def test_empty_snapshot_is_stable_and_carries_nothing() -> None:
    assert ContextSnapshot.empty().all_items() == []
    assert ContextSnapshot.empty().sha256() == ContextSnapshot().sha256()
