"""Public plan-first context bridge and plan-bound compilation (INV-CTX-045..047)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest

from l9_cognitive_runtime.cli import main as cli_main
from l9_cognitive_runtime.models.context import (
    AuthorityLevel,
    ContextKind,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    MemoryContext,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from tests.conftest import governed_signal_snapshot

GAR_REF = "runtime/kernels/architecture/global_architect_kernel.yaml"


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=15))


def _tool_data(result: Any) -> dict[str, Any]:
    assert result.is_error is False, getattr(result, "content", result)
    if getattr(result, "structured_content", None):
        return cast("dict[str, Any]", result.structured_content)
    return cast("dict[str, Any]", json.loads(result.content[0].text))


def _request(pack: Path, mission: str = "Update the greeting text.") -> CompileRequest:
    return CompileRequest(mission=mission, pack_root=pack)


def test_context_plan_is_deterministic_and_binds_semantic_sources(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    first = service.plan_context(_request(valid_pack))
    second = service.plan_context(_request(valid_pack))

    assert first == second
    assert first.context_plan_id.startswith("context-plan.sha256:")
    assert first.sha256() == second.sha256()
    assert first.pack_manifest_digest
    assert first.routing_rules_digest
    assert first.pipeline_digest
    assert first.active_kernel_digests
    assert first.requirement_plan.task_scope_digest == first.task_scope.sha256()


def test_matching_context_plan_binds_final_compile_and_packet(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    request = _request(valid_pack)
    plan = service.plan_context(request)

    bundle = service.compile_runtime(request, expected_context_plan_id=plan.context_plan_id)

    assert bundle.context_plan.context_plan_id == plan.context_plan_id
    assert bundle.packet["context_plan_id"] == plan.context_plan_id
    assert bundle.packet["provenance"]["context_plan_id"] == plan.context_plan_id
    assert bundle.digests()["context_plan"] == plan.sha256()


def test_changed_discovery_that_changes_route_or_kernels_requires_replan(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    request = _request(valid_pack)
    plan = service.plan_context(request)
    changed = governed_signal_snapshot("multiple_workers")

    with pytest.raises(InvalidValueError, match="replan required"):
        service.compile_runtime(
            request,
            context_snapshot=changed,
            expected_context_plan_id=plan.context_plan_id,
        )


def test_non_discovery_enrichment_does_not_invalidate_context_demand(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    request = _request(valid_pack)
    plan = service.plan_context(request)
    memory = MemoryContext(
        semantic_key="memory:prior-run",
        authority_level=AuthorityLevel.INFORMATIVE,
        source_ref=ContextSourceRef(
            source_id="memory",
            source_kind="semantic_memory",
            locator="memory://prior-run",
            immutable_coordinate="event:1",
        ),
        scope_mode=ContextScopeMode.GLOBAL,
        memory_id="memory:prior-run",
        memory_kind="execution_outcome",
    )

    bundle = service.compile_runtime(
        request,
        context_snapshot=ContextSnapshot(memory_context=[memory]),
        expected_context_plan_id=plan.context_plan_id,
    )

    assert bundle.context_plan.context_plan_id == plan.context_plan_id
    assert bundle.task_context.memory_context


def test_gar_declares_real_context_needs_that_enter_the_plan(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    plan = service.plan_context(
        _request(valid_pack),
        discovery_snapshot=governed_signal_snapshot("multiple_workers"),
    )

    assert GAR_REF in plan.active_kernel_digests
    kernel_requirements = [
        requirement
        for requirement in plan.requirement_plan.requirements
        if any(ref.startswith(f"{GAR_REF}#") for ref in requirement.kernel_need_refs)
    ]
    assert {requirement.context_kind for requirement in kernel_requirements} == {
        ContextKind.ARCHITECTURE_CONSTRAINT,
        ContextKind.DEPENDENCY_CONTEXT,
        ContextKind.PRIOR_DECISION,
    }


def test_adapter_projection_preserves_context_plan_identity(valid_pack: Path) -> None:
    from l9_cognitive_runtime.compiler.adapters import AdapterRenderer

    service = CognitiveRuntimeService()
    request = _request(valid_pack)
    plan = service.plan_context(request)
    bundle = service.compile_runtime(request, expected_context_plan_id=plan.context_plan_id)
    rendered = AdapterRenderer().render(bundle.packet, "claude_code")

    assert rendered.context_plan_id == plan.context_plan_id
    assert rendered.to_dict()["context_plan_id"] == plan.context_plan_id


def test_mcp_exposes_plan_and_accepts_plan_bound_compile(valid_pack: Path) -> None:
    from l9_cognitive_runtime.mcp import build_server

    server = build_server(valid_pack)
    planned = _tool_data(
        _run(server.call_tool("plan_context_requirements", {"mission": "Update greeting text."}))
    )
    compiled = _tool_data(
        _run(
            server.call_tool(
                "compile_runtime",
                {
                    "mission": "Update greeting text.",
                    "expected_context_plan_id": planned["context_plan_id"],
                },
            )
        )
    )

    assert planned["context_plan"]["schema_version"] == "l9.context-plan/v1"
    assert compiled["context_plan_id"] == planned["context_plan_id"]
    assert compiled["execution_packet"]["context_plan_id"] == planned["context_plan_id"]


def test_cli_plan_context_is_machine_readable(
    valid_pack: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli_main(
        [
            "--mission",
            "Update greeting text.",
            "--pack-root",
            str(valid_pack),
            "--plan-context",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context_plan_id"] == payload["context_plan"]["context_plan_id"]
    assert payload["context_plan"]["schema_version"] == "l9.context-plan/v1"


def test_cli_rejects_plan_output_with_expected_plan_binding(
    valid_pack: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main(
            [
                "--mission",
                "Update greeting text.",
                "--pack-root",
                str(valid_pack),
                "--plan-context",
                "--expected-context-plan-id",
                "context-plan.sha256:not-applicable",
            ]
        )

    assert exc_info.value.code == 2
    assert (
        "--expected-context-plan-id cannot be used with --plan-context" in capsys.readouterr().err
    )


def test_public_context_contract_schemas_ship_and_match_models() -> None:
    from l9_cognitive_runtime.models.context import ContextPlan

    contracts = Path(__file__).resolve().parents[1] / "contracts"
    for name, model in (
        ("context_snapshot.schema.json", ContextSnapshot),
        ("context_plan.schema.json", ContextPlan),
    ):
        shipped = json.loads((contracts / name).read_text(encoding="utf-8"))
        generated = model.model_json_schema(mode="serialization")
        for key, value in generated.items():
            assert shipped[key] == value, (name, key)


def test_context_plan_validates_against_public_schema(valid_pack: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    contracts = Path(__file__).resolve().parents[1] / "contracts"
    plan = CognitiveRuntimeService().plan_context(_request(valid_pack))
    schema = json.loads((contracts / "context_plan.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(plan.to_canonical_dict(), schema)
