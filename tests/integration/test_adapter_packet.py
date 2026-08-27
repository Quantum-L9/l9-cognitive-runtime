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
