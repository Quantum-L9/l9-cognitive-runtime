"""PHASE-07 gate evidence: adapter/provider boundary (INV-012/013, A0701-A0704).

Gate coverage:

- adapter_packet_preserves_all_required_obligation_ids;
- adapter_packet_preserves_GAR_outputs_or_resolvable_refs;
- adapter_packet_preserves_validation_properties;
- adapter_packet_preserves_delivery_requirements;
- MCP_writes_false / MCP_execution_false / MCP_shell_false;
- LIVE-007: a packet missing a blocking architecture obligation fails
  adapter validation;
- A0704: required unsupported obligations block execution with a governed
  handoff; receipt digests are verified.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.compiler.adapters import (
    AdapterRenderer,
    validate_packet,
)
from l9_cognitive_runtime.compiler.providers import (
    ProviderAcceptance,
    acceptance_receipt_digest,
    validate_provider_acceptance,
)
from l9_cognitive_runtime.mcp import build_server
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def _gar_packet(valid_pack: Path) -> dict[str, Any]:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(
            mission="Add safe retry behavior to this asynchronous payment worker.",
            pack_root=valid_pack,
            source_context={
                "pack": "test",
                "context_signals": [
                    "message_redelivery_possible",
                    "external_side_effect",
                    "multiple_workers",
                ],
            },
        )
    )
    return bundle.packet


def test_adapter_preserves_all_required_obligations(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    required_ids = {o["obligation_id"] for o in packet["required_obligations"]}
    assert "OBL.ARCHITECTURE" in required_ids
    for adapter in ("claude_code", "cursor", "codex", "chatgpt", "human_operator"):
        rendered = AdapterRenderer().render(packet, adapter)
        assert set(rendered.required_obligation_ids) == required_ids, adapter
        assert "OBL.ARCHITECTURE" in rendered.content


def test_adapter_preserves_gar_outputs_and_validation_and_delivery(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    renderer = AdapterRenderer()
    for adapter in ("claude_code", "cursor"):
        rendered = renderer.render(packet, adapter)
        expected_gar = {
            "GAR_ARCHITECTURE_DECISION",
            "GAR_ARCHITECTURAL_INTEGRITY_EVIDENCE",
            "GAR_PLAN_READINESS",
            "GAR_SYSTEM_MODEL",
            "GAR_TYPED_DEFECTS",
        }
        assert set(rendered.gar_output_refs) == expected_gar
        assert rendered.validation_properties
        assert rendered.delivery_obligations
        assert rendered.delivery_obligations[0]["obligation_id"] == "OBL.DELIVERY"
        assert rendered.unknowns == tuple(packet["unknowns"])
        assert rendered.packet_digest


def test_adapter_render_is_deterministic(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    first = AdapterRenderer().render(packet, "cursor")
    second = AdapterRenderer().render(packet, "cursor")
    assert first.to_dict() == second.to_dict()


def test_adapter_validation_fails_when_gar_binding_missing(valid_pack: Path) -> None:
    # LIVE-007: drop the GAR binding while the architecture obligation
    # remains — adapter validation must fail (no silent weakening).
    packet = _gar_packet(valid_pack)
    weakened = copy.deepcopy(packet)
    weakened["active_kernel_bindings"] = [
        b
        for b in weakened["active_kernel_bindings"]
        if not b["source_ref"].endswith("global_architect_kernel.yaml")
    ]
    with pytest.raises(InvalidValueError, match="GAR binding missing"):
        validate_packet(weakened)


def test_adapter_validation_fails_when_obligations_dropped(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    weakened = copy.deepcopy(packet)
    weakened["required_obligations"] = [
        o for o in weakened["required_obligations"] if o["obligation_id"] != "OBL.DELIVERY"
    ]
    with pytest.raises(InvalidValueError):
        AdapterRenderer().render(weakened, "cursor")


def test_mcp_remains_read_only_with_packet_resource(valid_pack: Path) -> None:
    """A0703 + INV-012: the packet is resolvable per run; the surface stays
    read-only (writes/execution/shell all false)."""
    import asyncio

    from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS

    server = build_server(valid_pack)

    async def _run() -> tuple[dict[str, Any], dict[str, Any], set[str]]:
        caps_raw = await server.call_tool("runtime_capabilities", {})
        caps = _tool_data(caps_raw)
        compiled = _tool_data(
            await server.call_tool(
                "compile_runtime",
                {
                    "mission": "Add safe retry behavior to this asynchronous payment worker.",
                    "task_type": "kernel_runtime_convergence",
                },
            )
        )
        tools = await server.list_tools()
        return caps, compiled, {tool.name for tool in tools}

    caps, compiled, tool_names = asyncio.run(_run())
    assert caps["writes"] is False
    assert caps["execution"] is False
    assert caps["shell"] is False
    assert tool_names == set(READ_ONLY_TOOLS)
    # The immutable per-run packet is resolvable and complete.
    packet = compiled["execution_packet"]
    assert packet["required_obligations"]
    assert packet["convergence_contract"]
    resource_parts = list(asyncio.run(server.read_resource(compiled["resource_uri"])))
    text = "".join(str(getattr(part, "content", "")) for part in resource_parts)
    payload = json.loads(text)
    assert payload["execution_packet"] == packet


def _tool_data(result: Any) -> dict[str, Any]:
    """Extract structured tool data from an MCP call result."""
    assert not getattr(result, "is_error", True), getattr(result, "content", result)
    structured = getattr(result, "structured_content", None)
    if structured:
        return dict(structured)
    parts = getattr(result, "content", [])
    text = "".join(str(getattr(part, "text", "")) for part in parts)
    return dict(json.loads(text))


def test_provider_acceptance_executes_when_all_accepted(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    required_ids = {o["obligation_id"] for o in packet["required_obligations"]}
    acceptance = ProviderAcceptance(
        provider_id="capable-host",
        accepted_obligation_ids=tuple(sorted(required_ids)),
        unsupported_obligation_ids=(),
        capabilities=("files", "shell"),
        authority_limits=("no_network",),
        receipt_digest="",
    )
    acceptance = ProviderAcceptance(
        provider_id=acceptance.provider_id,
        accepted_obligation_ids=acceptance.accepted_obligation_ids,
        unsupported_obligation_ids=acceptance.unsupported_obligation_ids,
        capabilities=acceptance.capabilities,
        authority_limits=acceptance.authority_limits,
        receipt_digest=acceptance_receipt_digest(packet, acceptance),
    )
    result = validate_provider_acceptance(packet, acceptance)
    assert result["executable"] is True


def test_provider_acceptance_blocks_on_unsupported_required(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    required_ids = {o["obligation_id"] for o in packet["required_obligations"]}
    unsupported = {"OBL.DELIVERY"}
    accepted = required_ids - unsupported
    acceptance = ProviderAcceptance(
        provider_id="partial-host",
        accepted_obligation_ids=tuple(sorted(accepted)),
        unsupported_obligation_ids=tuple(sorted(unsupported)),
        capabilities=("files",),
        authority_limits=("read_only",),
        receipt_digest="",
    )
    acceptance = ProviderAcceptance(
        provider_id=acceptance.provider_id,
        accepted_obligation_ids=acceptance.accepted_obligation_ids,
        unsupported_obligation_ids=acceptance.unsupported_obligation_ids,
        capabilities=acceptance.capabilities,
        authority_limits=acceptance.authority_limits,
        receipt_digest=acceptance_receipt_digest(packet, acceptance),
    )
    result = validate_provider_acceptance(packet, acceptance)
    assert result["executable"] is False
    assert result["block"]["type"] == "CAPABILITY"
    assert "OBL.DELIVERY" in result["block"]["unsupported_required_obligation_ids"]
    assert result["block"]["governed_handoff"]


def test_provider_receipt_digest_mismatch_fails(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    required_ids = {o["obligation_id"] for o in packet["required_obligations"]}
    acceptance = ProviderAcceptance(
        provider_id="tampered-host",
        accepted_obligation_ids=tuple(sorted(required_ids)),
        unsupported_obligation_ids=(),
        capabilities=(),
        authority_limits=(),
        receipt_digest="0" * 64,
    )
    with pytest.raises(InvalidValueError, match="digest mismatch"):
        validate_provider_acceptance(packet, acceptance)
