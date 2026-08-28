"""End-to-end context-native compilation.

ContextSnapshot -> CompilePipeline -> CompiledTaskContext -> RuntimeBundle ->
ExecutionPacket -> AdapterPacket, over a real verified pack.

Covers A003, A004, A005, A007, A008, A025, A029-A031, A036-A040, A045-A047,
A052, and A063.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.compiler.adapters import ADAPTER_TEMPLATES, AdapterRenderer
from l9_cognitive_runtime.models.context import (
    AuthorityFact,
    AuthorityLevel,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    EffectiveAuthorityOrderSource,
    MemoryContext,
    RepositoryState,
    UnknownMateriality,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle

MISSION = "Update the owner record for the payment module."


def source(source_id: str, coordinate: str = "rev-7") -> ContextSourceRef:
    return ContextSourceRef(
        source_id=source_id,
        source_kind="repository",
        locator=f"repo://l9/{source_id}",
        immutable_coordinate=coordinate,
    )


def owner_fact(value: str = "team-payments", item_id: str = "repo.owner") -> RepositoryState:
    return RepositoryState(
        item_id=item_id,
        semantic_key="l9:src/payments.py:owner",
        authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
        source_ref=source(item_id),
        scope_mode=ContextScopeMode.SCOPED,
        scope_refs=["src/payments.py"],
        repository_id="l9",
        revision="rev-7",
        subject_ref="src/payments.py",
        fact_type="owner",
        value=value,
    )


def governed_snapshot(owner: str = "team-payments") -> ContextSnapshot:
    return ContextSnapshot(
        repository_state=[owner_fact(owner)],
        authority_facts=[
            AuthorityFact(
                item_id="auth.write",
                semantic_key="repository_write::",
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=source("auth.write"),
                scope_mode=ContextScopeMode.GLOBAL,
                authority_id="repository_write",
                state="granted",
                precedence=0,
            )
        ],
        memory_context=[
            MemoryContext(
                item_id="mem.1",
                semantic_key="prior-payment-work",
                authority_level=AuthorityLevel.INFORMATIVE,
                source_ref=ContextSourceRef(
                    source_id="mem.1", source_kind="recall", locator="memory://prior"
                ),
                scope_mode=ContextScopeMode.GLOBAL,
                memory_id="prior-payment-work",
                memory_kind="recall",
                content="this module was refactored last quarter",
                relevance_reason="same module",
            )
        ],
    )


def request_for(pack: Path) -> CompileRequest:
    return CompileRequest(
        mission=MISSION,
        pack_root=pack,
        source_context={"pack": "l9_cognitive_runtime", "target_refs": ["src/payments.py"]},
    )


def compile_with(pack: Path, snapshot: ContextSnapshot | None) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(request_for(pack), context_snapshot=snapshot)


# --------------------------------------------------------------------------
# A004 / A007 / A046: governed context is a separate, optional input.
# --------------------------------------------------------------------------


def test_context_snapshot_is_not_a_compile_request_field() -> None:
    assert "context_snapshot" not in CompileRequest.__dataclass_fields__


def test_a_pre_context_call_shape_still_compiles(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(request_for(valid_pack))
    assert bundle.task_context.task_scope.mission == MISSION
    assert bundle.task_context.repository_state == []


def test_none_and_empty_snapshot_are_the_same_governed_input(valid_pack: Path) -> None:
    implicit = compile_with(valid_pack, None)
    explicit = compile_with(valid_pack, ContextSnapshot.empty())
    assert implicit.digests()["context"] == explicit.digests()["context"]
    assert implicit.semantic_digest == explicit.semantic_digest


def test_the_keyword_snapshot_reaches_the_bundle_task_context(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    selected = {item.item_id for item in bundle.task_context.repository_state}
    assert selected == {"repo.owner"}
    assert bundle.task_context.repository_state[0].selected_because


# --------------------------------------------------------------------------
# A005: raw caller context cannot become governed truth.
# --------------------------------------------------------------------------


def test_a_raw_hint_cannot_establish_repository_truth(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(
            mission=MISSION,
            pack_root=valid_pack,
            source_context={
                "pack": "l9_cognitive_runtime",
                "target_refs": ["src/payments.py"],
                # A caller asserting facts directly. None of this may become
                # compiled repository, law, authority, or capability truth.
                "repository_state": [{"subject": "src/payments.py", "owner": "attacker"}],
                "applicable_law": [{"law_id": "FAKE", "statement": "anything goes"}],
                "authority_facts": [{"authority_id": "repository_write", "state": "granted"}],
            },
        )
    )
    context = bundle.task_context
    assert context.repository_state == []
    assert context.applicable_law == []
    assert context.authority.granted == []
    # The hint did narrow scope, which is all a hint may do.
    assert context.task_scope.target_refs == ["src/payments.py"]


# --------------------------------------------------------------------------
# A008 / A025 / A063: bounded spine, exact kernel identity, provenance.
# --------------------------------------------------------------------------


def test_context_kernels_equal_the_downstream_kernel_bindings(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    context_refs = [binding["source_ref"] for binding in bundle.task_context.selected_kernels]
    assert context_refs == list(bundle.execution.kernel_activation)
    assert (
        bundle.task_context.provenance.kernel_digests
        == ((bundle.execution.metadata or {})["kernel_digests"])
    )


def test_provenance_identifies_the_material_selected_items(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    provenance = bundle.task_context.provenance
    assert set(provenance.selected_item_digests) >= {"repo.owner", "auth.write"}
    assert provenance.task_scope_digest == bundle.task_context.task_scope.sha256()
    assert provenance.compiler_identity.package_version
    assert provenance.compiler_identity.semantics_version


def test_compiled_context_carries_no_digest_of_itself(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    payload = bundle.task_context.to_canonical_dict()
    assert "context_digest" not in payload["provenance"]
    assert bundle.digests()["context"] == bundle.task_context.sha256()


# --------------------------------------------------------------------------
# A012 / A036: semantic identity moves with material context only.
# --------------------------------------------------------------------------


def test_material_context_change_moves_the_bundle_semantic_digest(valid_pack: Path) -> None:
    before = compile_with(valid_pack, governed_snapshot("team-payments"))
    after = compile_with(valid_pack, governed_snapshot("team-platform"))
    # The mission text is byte-identical; only governed context changed.
    assert before.intent.sha256() == after.intent.sha256()
    assert before.digests()["context"] != after.digests()["context"]
    assert before.semantic_digest != after.semantic_digest


def test_an_irrelevant_snapshot_addition_moves_nothing(valid_pack: Path) -> None:
    lean = compile_with(valid_pack, governed_snapshot())
    noisy_snapshot = governed_snapshot()
    noisy_snapshot = noisy_snapshot.model_copy(
        update={
            "repository_state": [
                *noisy_snapshot.repository_state,
                RepositoryState(
                    item_id="repo.unrelated",
                    semantic_key="l9:infra/terraform/main.tf:owner",
                    authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                    source_ref=source("repo.unrelated"),
                    scope_mode=ContextScopeMode.SCOPED,
                    scope_refs=["infra/terraform/main.tf"],
                    repository_id="l9",
                    revision="rev-7",
                    subject_ref="infra/terraform/main.tf",
                    fact_type="owner",
                    value="team-infra",
                ),
            ]
        }
    )
    noisy = compile_with(valid_pack, noisy_snapshot)
    assert noisy_snapshot.audit_digest() != governed_snapshot().audit_digest()
    assert lean.digests()["context"] == noisy.digests()["context"]
    assert lean.semantic_digest == noisy.semantic_digest


def test_compilation_is_deterministic_across_repeated_runs(valid_pack: Path) -> None:
    first = compile_with(valid_pack, governed_snapshot())
    second = compile_with(valid_pack, governed_snapshot())
    assert first.task_context.to_canonical_json() == second.task_context.to_canonical_json()
    assert first.semantic_digest == second.semantic_digest


# --------------------------------------------------------------------------
# A029 / A028: authority order source is explicit.
# --------------------------------------------------------------------------


def test_governed_authority_order_supersedes_the_labelled_compiler_default(
    valid_pack: Path,
) -> None:
    default = compile_with(valid_pack, None)
    assert default.task_context.authority.effective_order_source is (
        EffectiveAuthorityOrderSource.COMPILER_DEFAULT
    )
    assert (default.execution.metadata or {})["authority_order_source"] == "compiler_default"

    governed = compile_with(valid_pack, governed_snapshot())
    assert governed.task_context.authority.effective_order_source is (
        EffectiveAuthorityOrderSource.GOVERNED_CONTEXT
    )
    assert governed.execution.authority_order == ["repository_write"]
    assert (governed.execution.metadata or {})["authority_order_source"] == "governed_context"


# --------------------------------------------------------------------------
# A030: material unknowns are conserved to the packet.
# --------------------------------------------------------------------------


def test_a_material_context_unknown_survives_into_obligations_and_the_packet(
    valid_pack: Path,
) -> None:
    # Two equally authoritative governed claims about the same key: an
    # unresolvable contradiction, not a choice.
    contradiction = ContextSnapshot(
        repository_state=[
            owner_fact("team-payments", item_id="repo.a"),
            owner_fact("team-platform", item_id="repo.b"),
        ]
    )
    bundle = compile_with(valid_pack, contradiction)
    material = [
        unknown
        for unknown in bundle.task_context.unresolved_unknowns
        if unknown.materiality is UnknownMateriality.BLOCKING
    ]
    assert material, "the contradiction must remain an unknown"

    obligation_ids = {o.obligation_id for o in bundle.execution.obligations}
    for unknown in material:
        assert f"OBL.EPISTEMIC.CONTEXT.{unknown.unknown_id}" in obligation_ids
        assert unknown.unknown_id in bundle.packet["unknowns"]

    # Conserved through handoff and validation too.
    handoff_ids = {o.obligation_id for o in bundle.handoff.obligations}
    validation_refs = {p.obligation_ref for p in bundle.validation.validation_properties}
    for unknown in material:
        assert f"OBL.EPISTEMIC.CONTEXT.{unknown.unknown_id}" in handoff_ids
        assert f"OBL.EPISTEMIC.CONTEXT.{unknown.unknown_id}" in validation_refs


# --------------------------------------------------------------------------
# A037 / A038 / A031: the packet carries context; adapters preserve identity.
# --------------------------------------------------------------------------


def test_the_packet_carries_the_context_and_a_matching_digest(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    packet = bundle.packet
    assert packet["compiled_task_context"] == bundle.task_context.to_canonical_dict()
    assert packet["compiled_task_context_digest"] == bundle.digests()["context"]
    assert packet["provenance"]["context_digest"] == bundle.digests()["context"]


@pytest.mark.parametrize("adapter", sorted(ADAPTER_TEMPLATES))
def test_every_adapter_projection_preserves_the_context_digest(
    valid_pack: Path, adapter: str
) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    rendered = AdapterRenderer(valid_pack).render(bundle.packet, adapter)
    assert rendered.context_digest == bundle.digests()["context"]
    assert rendered.to_dict()["context_digest"] == bundle.digests()["context"]


def test_an_adapter_cannot_render_a_packet_missing_its_context(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    stripped = {k: v for k, v in bundle.packet.items() if k != "compiled_task_context"}
    with pytest.raises(InvalidValueError, match="compiled_task_context"):
        AdapterRenderer(valid_pack).render(stripped, "claude_code")


def test_an_adapter_cannot_render_a_packet_whose_context_digest_was_swapped(
    valid_pack: Path,
) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    tampered = dict(bundle.packet)
    tampered["compiled_task_context_digest"] = "0" * 64
    with pytest.raises(InvalidValueError, match="disagrees with packet provenance"):
        AdapterRenderer(valid_pack).render(tampered, "claude_code")


# --------------------------------------------------------------------------
# A045 / A047: PR #39 semantics and deployment closure survive.
# --------------------------------------------------------------------------


def test_pre_context_bundle_surfaces_are_unchanged(valid_pack: Path) -> None:
    bundle = compile_with(valid_pack, governed_snapshot())
    digests = bundle.digests()
    assert {
        "intent",
        "execution",
        "validation",
        "handoff",
        "graph",
        "manifest",
        "semantic",
        "context",
    } == set(digests)
    assert bundle.graph.nodes
    assert bundle.execution.obligations
    assert bundle.validation.validation_properties


def test_supported_routes_compile_with_the_default_empty_snapshot(valid_pack: Path) -> None:
    from l9_cognitive_runtime.deployment import validate_deployment_closure

    closure = validate_deployment_closure(valid_pack)
    assert closure["count"] > 0
    # Every supported route compiled a context under the empty governed
    # snapshot, so a sealed deployment needs no external context source.
    assert set(closure["context_digests"]) == set(closure["routes_compiled"])
    assert all(len(digest) == 64 for digest in closure["context_digests"].values())


def test_the_context_schema_ships_in_the_deployment_schema_set() -> None:
    from l9_cognitive_runtime.deployment import _iter_schema_sources

    repo_root = Path(__file__).resolve().parents[2]
    assert "contracts/compiled_task_context.schema.json" in _iter_schema_sources(repo_root)
