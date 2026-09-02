"""Regression locks for file/path and compatibility-validator security boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from l9_cognitive_runtime.graph import validate_execution_graph_mapping

ROOT = Path(__file__).resolve().parents[1]


def _graph() -> dict[str, Any]:
    return {
        "graph_id": "graph.test",
        "source_contract": "contract.test",
        "nodes": [
            {
                "id": "a",
                "phase": "P0",
                "kernel_refs": [],
                "outputs": [],
            },
            {
                "id": "b",
                "phase": "P1",
                "kernel_refs": [],
                "outputs": [],
            },
        ],
        "edges": [{"from": "a", "to": "b", "reason": "step_order"}],
        "terminal_node": "b",
        "validation_gates": [],
    }


def test_serialized_graph_validation_is_canonical_and_in_process() -> None:
    assert validate_execution_graph_mapping(_graph()) == []

    missing_terminal = _graph()
    missing_terminal["terminal_node"] = "missing"
    assert "terminal_node missing from nodes" in validate_execution_graph_mapping(missing_terminal)

    cyclic = _graph()
    cyclic["edges"] = [
        {"from": "a", "to": "b", "reason": "step_order"},
        {"from": "b", "to": "a", "reason": "cycle"},
    ]
    assert any("cycle detected" in finding for finding in validate_execution_graph_mapping(cyclic))


def test_repository_validator_never_executes_a_script_from_user_root() -> None:
    text = (
        ROOT / "runtime/kernel_pipeline/validators/validate_intent_and_execution_graph.py"
    ).read_text(encoding="utf-8")
    assert "subprocess" not in text
    assert "validate_execution_graph_mapping" in text
    assert "validator root escapes repository" in text


def test_compatibility_file_io_uses_confined_boundaries() -> None:
    validator = (ROOT / "runtime/execution_graph/graph_validator.py").read_text(encoding="utf-8")
    visualizer = (ROOT / "runtime/execution_graph/graph_visualizer.py").read_text(encoding="utf-8")
    planner = (ROOT / "runtime/kernel_pipeline/planner/plan_activation.py").read_text(
        encoding="utf-8"
    )

    assert "confined_input_file" in validator
    assert "confined_input_file" in visualizer
    assert "output.relative_to(write_root)" in visualizer
    assert "output path escapes allow_write_root" in visualizer
    assert "confined_output_path" in planner
