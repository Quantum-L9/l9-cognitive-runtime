# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_integration_test_adapter_packet__py
# title: test adapter packet
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/integration/test_adapter_packet.py
# content_hash: af9d1ed9b8785c6f8c7babcc64fc001734a1f3ae03c14e062d427869d6504ca5
# token_cost_estimate: 453
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""LIVE-007: an adapter that omits the architectural integrity obligation
fails validation — weakening is never silent."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.compiler.adapters import AdapterRenderer
from l9_cognitive_runtime.models.errors import ModelValidationError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def _gar_packet(pack: Path) -> dict[str, Any]:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(
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
    )
    return bundle.packet


def test_live007_adapter_omitting_architecture_obligation_fails(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    weakened = copy.deepcopy(packet)
    weakened["required_obligations"] = [
        o for o in weakened["required_obligations"] if o["obligation_id"] != "OBL.ARCHITECTURE"
    ]
    with pytest.raises(ModelValidationError):
        AdapterRenderer().render(weakened, "cursor")


def test_live007_intact_packet_renders_all_adapters(valid_pack: Path) -> None:
    packet = _gar_packet(valid_pack)
    for adapter in ("claude_code", "cursor", "codex", "chatgpt", "human_operator"):
        rendered = AdapterRenderer().render(packet, adapter)
        assert "OBL.ARCHITECTURE" in rendered.required_obligation_ids
        assert "OBL.DELIVERY" in rendered.required_obligation_ids
