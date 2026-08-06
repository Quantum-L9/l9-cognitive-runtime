"""Contract-derived execution graph tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.graph import derive_execution_graph, topological_order
from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.models.errors import InvalidValueError

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "graph" / "execution_graph_golden.json"

GOLDEN_SEQUENCE = [
    "lock context",
    "run constitutional preflight",
    "run recursive improvement",
    "execute terminal doctrine only after gates pass",
]


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


def test_derived_graph_matches_golden() -> None:
    # Regression lock: a fixed contract yields a byte-identical canonical graph.
    graph = derive_execution_graph(_contract(GOLDEN_SEQUENCE))
    expected = GOLDEN.read_text(encoding="utf-8").rstrip("\n")
    assert graph.to_canonical_json() == expected


def test_nodes_and_edges_derive_from_sequence() -> None:
    graph = derive_execution_graph(_contract(GOLDEN_SEQUENCE))
    assert [n.id for n in graph.nodes] == [
        "front_end_intake",
        "semantic_preflight",
        "optimization",
        "emission",
    ]
    # Edges follow the declared order.
    assert [(e.from_node, e.to_node) for e in graph.edges] == [
        ("front_end_intake", "semantic_preflight"),
        ("semantic_preflight", "optimization"),
        ("optimization", "emission"),
    ]
    assert graph.terminal_node == "emission"


def test_validation_gates_derive_from_contract_no_default() -> None:
    graph = derive_execution_graph(_contract(["lock context"]))
    # Gates come straight from the contract (["format"]) — no fabricated default.
    assert graph.validation_gates == ["format"]


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
