"""Structured-execution-graph derivation tests (PHASE-05)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.graph import derive_execution_graph, topological_order
from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.models.errors import InvalidValueError

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "graph" / "execution_graph_golden.json"

GOLDEN_STEPS: list[dict[str, Any]] = [
    {
        "step_id": "step.P0_UNPACK",
        "phase": "P0_UNPACK",
        "kernel_refs": ["runtime/kernels/task/repo_auditor_kernel.yaml"],
        "obligation_refs": ["OBL.REALIZATION"],
        "input_refs": [],
        "output_refs": ["SYSTEM_MAP.md"],
        "entry_gates": [],
        "exit_gates": ["All relevant files inventoried."],
        "evidence_requirements": ["realization evidence"],
        "failure_routes": ["BLOCKED", "ABORTED"],
    },
    {
        "step_id": "step.P1_CONSTITUTIONAL_PREFLIGHT",
        "phase": "P1_CONSTITUTIONAL_PREFLIGHT",
        "kernel_refs": ["runtime/kernels/constitutional/K01-platform-architecture-engine.yaml"],
        "obligation_refs": ["OBL.AUTHORITY"],
        "input_refs": ["SYSTEM_MAP.md"],
        "output_refs": ["CONSTITUTIONAL_PREFLIGHT_REPORT.md"],
        "entry_gates": [],
        "exit_gates": ["No critical unresolved law."],
        "evidence_requirements": ["authority order respected with evidence"],
        "failure_routes": ["BLOCKED", "ABORTED"],
    },
    {
        "step_id": "step.P5_RECURSIVE_IMPROVEMENT",
        "phase": "P5_RECURSIVE_IMPROVEMENT",
        "kernel_refs": ["runtime/kernels/improvement/recursive_improvement.md"],
        "obligation_refs": ["OBL.VALIDATION"],
        "input_refs": ["CONSTITUTIONAL_PREFLIGHT_REPORT.md"],
        "output_refs": ["IMPROVEMENT_PATCH_PLAN.md"],
        "entry_gates": [],
        "exit_gates": ["Another pass adds no value."],
        "evidence_requirements": ["command run or blocker reason"],
        "failure_routes": ["BLOCKED", "ABORTED"],
    },
    {
        "step_id": "step.P7_FLAWLESS_VICTORY",
        "phase": "P7_FLAWLESS_VICTORY",
        "kernel_refs": ["runtime/kernels/terminal/flawless_victory.contract.yaml"],
        "obligation_refs": ["OBL.CONVERGENCE"],
        "input_refs": ["IMPROVEMENT_PATCH_PLAN.md"],
        "output_refs": ["VALIDATION_EVIDENCE.md"],
        "entry_gates": [],
        "exit_gates": ["Honest validation, no drift."],
        "evidence_requirements": ["terminal disposition receipt"],
        "failure_routes": ["ABORTED"],
    },
]


def _contract(
    steps: list[dict[str, Any]] | None = None,
    kernel_activation: list[str] | None = None,
) -> ExecutionContract:
    mapping: dict[str, Any] = {
        "contract_id": "C1",
        "contract_type": "universal_execution_contract",
        "source_activation_plan": "plan.yaml",
        "terminal_doctrine": "terminal.yaml",
        "objective": "derive graph",
        "authority_order": ["user task"],
        "kernel_activation": kernel_activation or ["runtime/kernels/task/repo_auditor_kernel.yaml"],
        "execution_sequence": ["lock context"],
        "validation_requirements": ["format"],
        "output_contract": ["summary"],
        "adapter_targets": ["cursor"],
    }
    if steps is not None:
        mapping["execution_steps"] = steps
    return ExecutionContract.from_mapping(mapping)


def test_contract_without_steps_rejected() -> None:
    # A0501: no prose decoding, no first-kernel fallback — structured steps
    # are the only graph source.
    with pytest.raises(InvalidValueError, match="execution_steps"):
        derive_execution_graph(_contract(steps=None))


def test_contract_changes_alter_graph() -> None:
    g1 = derive_execution_graph(_contract(steps=GOLDEN_STEPS[:2]))
    g2 = derive_execution_graph(_contract(steps=GOLDEN_STEPS[:3]))
    assert len(g1.nodes) == 2
    assert len(g2.nodes) == 3
    assert g1.sha256() != g2.sha256()


def test_identical_contracts_deterministic() -> None:
    a = derive_execution_graph(_contract(steps=GOLDEN_STEPS))
    b = derive_execution_graph(_contract(steps=GOLDEN_STEPS))
    assert a.to_canonical_json() == b.to_canonical_json()
    assert a.sha256() == b.sha256()


def test_derived_graph_matches_golden() -> None:
    # Regression lock: a fixed structured contract yields a byte-identical
    # canonical graph.
    graph = derive_execution_graph(_contract(steps=GOLDEN_STEPS))
    expected = GOLDEN.read_text(encoding="utf-8").rstrip("\n")
    assert graph.to_canonical_json() == expected


def test_nodes_and_edges_derive_from_steps() -> None:
    graph = derive_execution_graph(_contract(steps=GOLDEN_STEPS))
    assert [n.id for n in graph.nodes] == [
        "step.P0_UNPACK",
        "step.P1_CONSTITUTIONAL_PREFLIGHT",
        "step.P5_RECURSIVE_IMPROVEMENT",
        "step.P7_FLAWLESS_VICTORY",
    ]
    assert [(e.from_node, e.to_node) for e in graph.edges] == [
        ("step.P0_UNPACK", "step.P1_CONSTITUTIONAL_PREFLIGHT"),
        ("step.P1_CONSTITUTIONAL_PREFLIGHT", "step.P5_RECURSIVE_IMPROVEMENT"),
        ("step.P5_RECURSIVE_IMPROVEMENT", "step.P7_FLAWLESS_VICTORY"),
    ]
    assert graph.terminal_node == "step.P7_FLAWLESS_VICTORY"
    # A0503: the terminal node represents CONVERGED; other nodes route to
    # BLOCKED/ABORTED; the graph records the terminal disposition.
    terminal = graph.nodes[-1]
    assert terminal.disposition == "CONVERGED"
    assert terminal.failure_routes == ["ABORTED"]
    assert all("BLOCKED" in n.failure_routes for n in graph.nodes[:-1])
    assert graph.terminal_disposition == "CONVERGED"


def test_no_kernel_substitution() -> None:
    # The step's declared kernel_refs survive verbatim: no phase-map
    # substitution, no first-entry fallback.
    steps: list[dict[str, Any]] = [
        {
            **GOLDEN_STEPS[0],
            "step_id": "step.P2_TASK_ROUTING",
            "phase": "P2_TASK_ROUTING",
            "kernel_refs": ["runtime/kernels/task/developer_core_kernel.yaml"],
        }
    ]
    graph = derive_execution_graph(_contract(steps=steps))
    assert graph.nodes[0].kernel_refs == ["runtime/kernels/task/developer_core_kernel.yaml"]


def test_validation_gates_derive_from_contract_no_default() -> None:
    graph = derive_execution_graph(_contract(steps=GOLDEN_STEPS[:1]))
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
