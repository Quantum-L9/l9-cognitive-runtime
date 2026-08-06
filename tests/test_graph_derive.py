"""Contract-derived execution graph tests."""

from __future__ import annotations

import pytest

from l9_cognitive_runtime.graph import derive_execution_graph, topological_order
from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.models.errors import InvalidValueError


def _contract(sequence: list[str]) -> ExecutionContract:
    return ExecutionContract.from_mapping(
        {
            "contract_id": "C1",
            "contract_type": "universal_execution_contract",
            "source_activation_plan": "plan.yaml",
            "terminal_doctrine": "terminal.yaml",
            "objective": "derive graph",
            "authority_order": ["user task"],
            "kernel_activation": ["k1"],
            "execution_sequence": sequence,
            "validation_requirements": ["format"],
            "output_contract": ["summary"],
            "adapter_targets": ["cursor"],
        }
    )


def test_contract_changes_alter_graph() -> None:
    g1 = derive_execution_graph(_contract(["lock context", "run constitutional preflight"]))
    g2 = derive_execution_graph(
        _contract(
            [
                "lock context",
                "run constitutional preflight",
                "run recursive improvement",
            ]
        )
    )
    assert len(g1.nodes) == 2
    assert len(g2.nodes) == 3
    assert g1.sha256() != g2.sha256()


def test_identical_contracts_deterministic() -> None:
    seq = ["lock context", "run constitutional preflight", "emit evidence-backed final summary"]
    a = derive_execution_graph(_contract(seq))
    b = derive_execution_graph(_contract(seq))
    assert a.to_canonical_json() == b.to_canonical_json()
    assert a.sha256() == b.sha256()


def test_cycle_rejected() -> None:
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]
    with pytest.raises(InvalidValueError):
        topological_order(nodes, edges)


def test_missing_dependency_rejected() -> None:
    nodes = [{"id": "a"}]
    edges = [{"from": "a", "to": "missing"}]
    with pytest.raises(InvalidValueError):
        topological_order(nodes, edges)
