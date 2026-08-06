"""Tests for canonical typed models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from l9_cognitive_runtime.models import (
    AdapterRender,
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    InvalidValueError,
    UnknownFieldError,
    ValidationContract,
    canonical_json,
    dump_yaml,
    load_yaml,
    load_yaml_mapping,
    sha256_digest,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "models"


def test_intent_rejects_unknown_field() -> None:
    with pytest.raises(UnknownFieldError):
        IntentContract.from_mapping(
            {
                "intent_id": "i1",
                "mission": "do the thing",
                "task_type": "build",
                "constraints": [],
                "desired_outputs": ["x"],
                "not_in_schema": True,
            }
        )


def test_intent_rejects_empty_mission() -> None:
    with pytest.raises(InvalidValueError):
        IntentContract.from_mapping(
            {
                "intent_id": "i1",
                "mission": "",
                "task_type": "build",
                "constraints": [],
                "desired_outputs": ["x"],
            }
        )


def test_canonical_json_and_digest_stable() -> None:
    model = IntentContract.from_mapping(
        {
            "intent_id": "i1",
            "mission": "do the thing",
            "task_type": "build",
            "constraints": ["a", "b"],
            "desired_outputs": ["out"],
            "unknowns": ["u1"],
            "source_context": {"z": 1, "a": 2},
        }
    )
    first = model.to_canonical_json()
    second = model.to_canonical_json()
    assert first == second
    assert first == canonical_json(json.loads(first))
    assert model.sha256() == sha256_digest(json.loads(first))
    assert FIXTURES.joinpath("intent_canonical.json").read_text(encoding="utf-8").strip() == first
    digest = FIXTURES.joinpath("intent_digest.txt").read_text(encoding="utf-8").strip()
    assert digest == model.sha256()


def test_yaml_uses_serializer_roundtrip() -> None:
    model = ValidationContract.from_mapping(
        {
            "contract_id": "VALIDATION_CONTRACT",
            "contract_type": "validation_contract",
            "validation_ladder": ["format", "schema"],
            "evidence_required": ["status"],
            "allowed_statuses": ["passed", "failed"],
        }
    )
    text = dump_yaml(model)
    loaded = load_yaml(ValidationContract, text)
    assert loaded.to_canonical_json() == model.to_canonical_json()
    assert "contract_id: VALIDATION_CONTRACT" in text


def test_empty_yaml_document_rejected() -> None:
    with pytest.raises(InvalidValueError, match="empty"):
        load_yaml_mapping("")
    with pytest.raises(InvalidValueError, match="empty"):
        load_yaml(ValidationContract, "null\n")


def test_repo_execution_contract_loads() -> None:
    data = yaml.safe_load((ROOT / "FINAL_EXECUTION_CONTRACT.yaml").read_text(encoding="utf-8"))
    model = ExecutionContract.from_mapping(data)
    assert model.contract_type == "universal_execution_contract"
    assert "claude_code" in model.adapter_targets


def test_repo_validation_contract_loads() -> None:
    data = yaml.safe_load((ROOT / "VALIDATION_CONTRACT.yaml").read_text(encoding="utf-8"))
    model = ValidationContract.from_mapping(data)
    assert model.contract_id == "VALIDATION_CONTRACT"


def test_repo_handoff_null_unknowns_coerced() -> None:
    data = yaml.safe_load((ROOT / "HANDOFF_CONTRACT.yaml").read_text(encoding="utf-8"))
    model = HandoffContract.from_mapping(data)
    assert model.unknowns == []


def test_repo_execution_graph_loads() -> None:
    data = json.loads((ROOT / "EXECUTION_GRAPH.json").read_text(encoding="utf-8"))
    model = ExecutionGraph.from_mapping(data)
    assert model.graph_id == "l9_execution_graph.v1"
    assert model.edges[0].from_node


def test_adapter_render_enum() -> None:
    model = AdapterRender.from_mapping(
        {
            "adapter": "cursor",
            "source_contract": "FINAL_EXECUTION_CONTRACT",
            "render_type": "task",
            "content": "do work",
        }
    )
    assert model.adapter.value == "cursor"
