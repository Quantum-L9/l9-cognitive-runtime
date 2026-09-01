"""Context-native compilation at integration scope.

Covers the seams where a context-native compile can look correct and be wrong:
a required kernel output that is declared but never realized, a packet whose
context digest nothing verifies against the body it carries, an adapter that
keeps the digest but loses the context, and a public surface that cannot accept
governed context at all.
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.adapters import AdapterRenderer, validate_packet
from l9_cognitive_runtime.compiler.context_closure import CONTEXT_CHECKS, ContextClosureReport
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.liveness import validate_runtime_semantic_liveness
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.graph import derive_execution_graph
from l9_cognitive_runtime.models.context import ContextSnapshot
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle
from tests.conftest import discovery_for, governed_signal_snapshot

GAR_REF = "runtime/kernels/architecture/global_architect_kernel.yaml"
MISSION = "Add safe retry behavior to this asynchronous payment worker."
GOVERNED_SIGNALS = ("message_redelivery_possible", "external_side_effect", "multiple_workers")


def snapshot() -> ContextSnapshot:
    return governed_signal_snapshot(*GOVERNED_SIGNALS)


def request_for(pack: Path) -> CompileRequest:
    return CompileRequest(mission=MISSION, pack_root=pack, source_context={"pack": "test"})


def default_request_for(pack: Path) -> CompileRequest:
    """The request shape the CLI and MCP surfaces build for the same mission.

    ``source_context`` is part of the intent contract and therefore part of the
    intent digest, so a cross-surface equivalence test has to hold it constant —
    otherwise it measures the request, not the compiler.
    """
    return CompileRequest(mission=MISSION, pack_root=pack)


def compile_default(pack: Path) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(
        default_request_for(pack), context_snapshot=snapshot()
    )


def compile_bundle(pack: Path) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(request_for(pack), context_snapshot=snapshot())


def liveness_kwargs(bundle: RuntimeBundle, pack: Path, **overrides: Any) -> dict[str, Any]:
    intent = ObjectiveDeriver().derive(request_for(pack))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
        discovery=discovery_for(intent, snapshot()),
    )
    context_digest = bundle.digests()["context"]
    kwargs: dict[str, Any] = {
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
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# INV-CTX-039: every_required_kernel_output_exists is a real semantic check.
# ---------------------------------------------------------------------------


def test_the_live_bundle_realizes_every_required_kernel_output(valid_pack: Path) -> None:
    bundle = compile_bundle(valid_pack)
    kernels = KernelResolver().resolve(list(bundle.execution.kernel_activation), valid_pack)
    gar = next(binding for binding in kernels if binding.source_ref == GAR_REF)
    required = {output.output_id for output in gar.outputs if output.required}
    assert required, "the GAR kernel must declare required outputs for this to mean anything"
    realized = {
        ref
        for step in bundle.execution.execution_steps
        if GAR_REF in step.kernel_refs
        for ref in step.output_refs
    }
    assert required <= realized
    assert validate_runtime_semantic_liveness(**liveness_kwargs(bundle, valid_pack)).passed


def test_dropping_a_required_kernel_output_from_the_step_fails_liveness(
    valid_pack: Path,
) -> None:
    bundle = compile_bundle(valid_pack)
    steps = []
    dropped: str | None = None
    for step in bundle.execution.execution_steps:
        if GAR_REF in step.kernel_refs and dropped is None:
            dropped = "GAR_SYSTEM_MODEL"
            steps.append(
                step.model_copy(
                    update={"output_refs": [o for o in step.output_refs if o != dropped]}
                )
            )
        else:
            steps.append(step)
    assert dropped is not None, "the GAR kernel must be invoked by a step"
    execution = bundle.execution.model_copy(update={"execution_steps": steps})
    graph = derive_execution_graph(execution)
    with pytest.raises(InvalidValueError, match="every_required_kernel_output_exists"):
        validate_runtime_semantic_liveness(
            **liveness_kwargs(bundle, valid_pack, execution=execution, graph=graph)
        )


def test_dropping_a_required_kernel_output_from_the_graph_fails_liveness(
    valid_pack: Path,
) -> None:
    """Preservation into the graph is verified, not assumed from derivation."""
    bundle = compile_bundle(valid_pack)
    nodes = [
        node.model_copy(update={"outputs": [o for o in node.outputs if o != "GAR_SYSTEM_MODEL"]})
        if GAR_REF in node.kernel_refs
        else node
        for node in bundle.graph.nodes
    ]
    graph = bundle.graph.model_copy(update={"nodes": nodes})
    with pytest.raises(InvalidValueError, match="every_required_kernel_output_exists"):
        validate_runtime_semantic_liveness(**liveness_kwargs(bundle, valid_pack, graph=graph))


# ---------------------------------------------------------------------------
# INV-CTX-030 / INV-CTX-031: the packet carries the context, verifiably.
# ---------------------------------------------------------------------------


def test_the_packet_carries_the_context_body_and_a_matching_digest(valid_pack: Path) -> None:
    bundle = compile_bundle(valid_pack)
    packet = bundle.packet
    assert packet["compiled_task_context"] == bundle.task_context.to_canonical_dict()
    assert packet["compiled_task_context_digest"] == bundle.digests()["context"]
    assert packet["provenance"]["context_digest"] == bundle.digests()["context"]


def test_a_mutated_context_body_fails_packet_validation(valid_pack: Path) -> None:
    """The declared digest is unchanged; only the body moved."""
    bundle = compile_bundle(valid_pack)
    tampered = copy.deepcopy(bundle.packet)
    tampered["compiled_task_context"]["task_scope"]["mission"] = "a different mission entirely"
    assert tampered["compiled_task_context_digest"] == bundle.packet["compiled_task_context_digest"]
    with pytest.raises(InvalidValueError, match="does not hash to its declared digest"):
        validate_packet(tampered)


def test_a_context_digest_disagreeing_with_provenance_fails_packet_validation(
    valid_pack: Path,
) -> None:
    bundle = compile_bundle(valid_pack)
    tampered = copy.deepcopy(bundle.packet)
    tampered["provenance"]["context_digest"] = "0" * 64
    with pytest.raises(InvalidValueError, match="disagrees with packet provenance"):
        validate_packet(tampered)


def test_the_adapter_projection_preserves_the_context_body_exactly(valid_pack: Path) -> None:
    bundle = compile_bundle(valid_pack)
    for adapter in ("claude_code", "cursor", "codex", "chatgpt", "human_operator"):
        rendered = AdapterRenderer().render(bundle.packet, adapter)
        assert rendered.compiled_task_context == bundle.packet["compiled_task_context"]
        assert rendered.context_digest == bundle.digests()["context"]


def test_the_adapter_projection_preserves_law_authority_and_gaps(valid_pack: Path) -> None:
    """A projection that keeps only the digest would pass a digest check and
    still have lost everything that matters."""
    from tests.test_context_compiler import law  # governed law builder

    bundle = CognitiveRuntimeService().compile_runtime(
        request_for(valid_pack),
        context_snapshot=ContextSnapshot(
            architecture_constraints=list(snapshot().architecture_constraints),
            applicable_law=[law("LAW_RETRY")],
        ),
    )
    rendered = AdapterRenderer().render(bundle.packet, "claude_code")
    assert "LAW_RETRY" in rendered.applicable_law_refs
    # Required capabilities with no proof are gaps, and they survive projection.
    assert rendered.capability_gap_refs
    assert set(rendered.capability_gap_refs) == {
        requirement.capability_id for requirement in bundle.task_context.capabilities.required
    }
    assert set(rendered.context_unknown_ids) == {
        unknown.unknown_id for unknown in bundle.task_context.unresolved_unknowns
    }
    # The textual rendering references the canonical context rather than
    # re-deriving it.
    assert bundle.digests()["context"] in rendered.content
    assert "LAW_RETRY" in rendered.content


def test_no_adapter_reselects_or_recomputes_context() -> None:
    """The renderer reads the packet's context; it never rebuilds one."""
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "l9_cognitive_runtime"
        / "compiler"
        / "adapters.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("ContextCompiler", "resolve_snapshot", "ContextRequirementPlanner"):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# INV-CTX-029: the context digest participates in runtime semantic identity.
# ---------------------------------------------------------------------------


def test_the_bundle_exposes_a_context_digest(valid_pack: Path) -> None:
    digests = compile_bundle(valid_pack).digests()
    assert len(digests["context"]) == 64


def test_the_semantic_digest_moves_with_material_context(valid_pack: Path) -> None:
    from tests.test_context_compiler import law

    base = compile_bundle(valid_pack)
    extended = CognitiveRuntimeService().compile_runtime(
        request_for(valid_pack),
        context_snapshot=ContextSnapshot(
            architecture_constraints=list(snapshot().architecture_constraints),
            applicable_law=[law("LAW_EXTRA")],
        ),
    )
    assert extended.digests()["context"] != base.digests()["context"]
    assert extended.digests()["semantic"] != base.digests()["semantic"]


def test_recompiling_the_same_input_is_byte_identical(valid_pack: Path) -> None:
    first = compile_bundle(valid_pack)
    second = compile_bundle(valid_pack)
    assert first.digests() == second.digests()
    assert first.task_context.to_canonical_dict() == second.task_context.to_canonical_dict()


# ---------------------------------------------------------------------------
# INV-CTX-007: the snapshot preflight runs before resolution.
# ---------------------------------------------------------------------------


def test_resolve_snapshot_is_not_reached_after_a_preflight_rejection(
    valid_pack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from l9_cognitive_runtime.compiler import pipeline as pipeline_module
    from l9_cognitive_runtime.models.context import SNAPSHOT_MAX_ITEMS
    from tests.test_context_models import entity

    called: list[object] = []

    def _spy(snap: object) -> None:
        called.append(snap)

    monkeypatch.setattr(pipeline_module, "resolve_snapshot", _spy)
    oversized = ContextSnapshot(
        relevant_entities=[entity(f"m{index:04d}") for index in range(SNAPSHOT_MAX_ITEMS + 1)]
    )
    with pytest.raises(InvalidValueError, match="maximum item count"):
        CognitiveRuntimeService().compile_runtime(
            request_for(valid_pack), context_snapshot=oversized
        )
    assert called == []


# ---------------------------------------------------------------------------
# INV-CTX-043: every public surface can receive governed context.
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=30))


def _tool_data(result: Any) -> dict[str, Any]:
    assert result.is_error is False, getattr(result, "content", result)
    if getattr(result, "structured_content", None):
        return cast("dict[str, Any]", result.structured_content)
    return cast("dict[str, Any]", json.loads(result.content[0].text))


def test_python_and_mcp_produce_the_same_semantics_for_the_same_input(
    valid_pack: Path,
) -> None:
    from l9_cognitive_runtime.mcp import build_server

    native = compile_default(valid_pack)
    server = build_server(valid_pack)
    result = _tool_data(
        _run(
            server.call_tool(
                "compile_runtime",
                {
                    "mission": MISSION,
                    "context_snapshot": snapshot().to_canonical_dict(),
                },
            )
        )
    )
    assert result["digests"]["context"] == native.digests()["context"]
    assert result["digests"]["semantic"] == native.digests()["semantic"]
    assert (
        result["execution_packet"]["compiled_task_context"]
        == native.packet["compiled_task_context"]
    )


def test_the_cli_accepts_a_governed_context_snapshot(
    valid_pack: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from l9_cognitive_runtime.cli import main as cli_main

    payload = tmp_path / "snapshot.json"
    payload.write_text(json.dumps(snapshot().to_canonical_dict()), encoding="utf-8")
    assert (
        cli_main(
            [
                "--mission",
                MISSION,
                "--pack-root",
                str(valid_pack),
                "--context-snapshot",
                str(payload),
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    native = compile_default(valid_pack)
    assert out["digests"] == native.digests()
    assert out["compiled_task_context"] == native.task_context.to_canonical_dict()


def test_the_cli_fails_closed_on_a_malformed_snapshot(valid_pack: Path, tmp_path: Path) -> None:
    from l9_cognitive_runtime.cli import main as cli_main

    payload = tmp_path / "snapshot.json"
    payload.write_text(json.dumps({"applicable_law": [{"law_id": "LAW_X"}]}), encoding="utf-8")
    with pytest.raises(InvalidValueError, match="not a valid governed snapshot"):
        cli_main(
            [
                "--mission",
                MISSION,
                "--pack-root",
                str(valid_pack),
                "--context-snapshot",
                str(payload),
            ]
        )


def test_the_mcp_surface_fails_closed_on_a_malformed_snapshot(valid_pack: Path) -> None:
    from l9_cognitive_runtime.mcp import build_server

    server = build_server(valid_pack)
    with pytest.raises(Exception):  # noqa: B017 - the SDK wraps it as a tool error
        _run(
            server.call_tool(
                "compile_runtime",
                {"mission": MISSION, "context_snapshot": {"applicable_law": [{"nope": 1}]}},
            )
        )


def test_mcp_activation_planning_accepts_context_because_context_routes(
    valid_pack: Path,
) -> None:
    from l9_cognitive_runtime.mcp import build_server

    server = build_server(valid_pack)
    plain = _tool_data(
        _run(server.call_tool("plan_kernel_activation", {"mission": "Update the greeting text."}))
    )
    governed = _tool_data(
        _run(
            server.call_tool(
                "plan_kernel_activation",
                {
                    "mission": "Update the greeting text.",
                    "context_snapshot": governed_signal_snapshot(
                        "multiple_workers"
                    ).to_canonical_dict(),
                },
            )
        )
    )
    assert GAR_REF not in plain["kernel_activation"]
    assert GAR_REF in governed["kernel_activation"]
    assert governed["context_digest"] != plain["context_digest"]


def test_mcp_bundle_validation_accepts_context_and_checks_the_packet(
    valid_pack: Path,
) -> None:
    from l9_cognitive_runtime.mcp import build_server

    server = build_server(valid_pack)
    data = _tool_data(
        _run(
            server.call_tool(
                "validate_runtime_bundle",
                {"mission": MISSION, "context_snapshot": snapshot().to_canonical_dict()},
            )
        )
    )
    assert data["valid"] is True
    assert data["checks"]["packet_context_digest_matches"] is True


def test_runtime_capabilities_advertise_governed_context_input(valid_pack: Path) -> None:
    from l9_cognitive_runtime.mcp import CONTEXT_AWARE_TOOLS, build_server

    server = build_server(valid_pack)
    data = _tool_data(_run(server.call_tool("runtime_capabilities", {})))
    assert data["context_snapshot_input"] is True
    assert set(data["context_aware_tools"]) == set(CONTEXT_AWARE_TOOLS)


def test_http_does_not_reinterpret_context() -> None:
    """HTTP is a transport for the MCP surface, not a second interpreter."""
    source = (
        Path(__file__).resolve().parents[2] / "src" / "l9_cognitive_runtime" / "mcp" / "http.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("ContextSnapshot", "parse_context_snapshot", "compiled_task_context"):
        assert forbidden not in source


def test_host_surfaces_reject_an_oversized_payload_before_typing_it(
    valid_pack: Path, tmp_path: Path
) -> None:
    """Typing a candidate hashes it, so the ceiling applies to the raw payload."""
    from l9_cognitive_runtime.cli import main as cli_main
    from l9_cognitive_runtime.mcp import parse_context_snapshot
    from l9_cognitive_runtime.models.context import SNAPSHOT_MAX_ITEMS

    oversized = {
        "relevant_entities": [
            {"not": "even a valid candidate"} for _ in range(SNAPSHOT_MAX_ITEMS + 1)
        ]
    }
    # The payload is not merely oversized, it is unparseable — so a surface that
    # typed first would fail on shape rather than on the ceiling.
    with pytest.raises(InvalidValueError, match="maximum item count"):
        parse_context_snapshot(oversized)

    payload = tmp_path / "oversized.json"
    payload.write_text(json.dumps(oversized), encoding="utf-8")
    with pytest.raises(InvalidValueError, match="maximum item count"):
        cli_main(
            [
                "--mission",
                MISSION,
                "--pack-root",
                str(valid_pack),
                "--context-snapshot",
                str(payload),
            ]
        )
