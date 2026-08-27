"""Derive execution graphs from structured execution contracts.

This is a pure, deterministic transform of an ``ExecutionContract`` into an
``ExecutionGraph`` — not a runtime scheduler. Nodes derive mechanically from
the contract's structured ``execution_steps`` (INV-006): kernel references,
obligation references, gates, evidence requirements, and failure routes come
from the step declarations. There is no prose phase map and no first-kernel
fallback; a contract without structured steps cannot derive a graph (A0501).
Cycles and unresolved dependencies are rejected, and identical contracts
produce byte-identical canonical graphs.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from l9_cognitive_runtime.models import ExecutionContract, ExecutionGraph
from l9_cognitive_runtime.models.errors import InvalidValueError

# Run-level exits every step may route to (A0503): a step can fail closed into
# a block or an abort; the terminal node additionally represents CONVERGED.
BLOCKED = "BLOCKED"
ABORTED = "ABORTED"
CONVERGED = "CONVERGED"


def derive_execution_graph(contract: ExecutionContract) -> ExecutionGraph:
    """Build a deterministic graph from a contract's structured steps."""
    steps = contract.execution_steps
    if not steps:
        raise InvalidValueError(
            "execution_steps required to derive graph",
            path="execution_steps",
        )

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    ordered_ids: list[str] = []
    terminal_phase = "P7_FLAWLESS_VICTORY"

    for step in steps:
        node_id = step.step_id
        if node_id in seen_ids:
            raise InvalidValueError(
                "duplicate execution step id",
                path="execution_steps",
                details={"step_id": node_id},
            )
        seen_ids.add(node_id)
        ordered_ids.append(node_id)
        is_terminal = step.phase == terminal_phase
        nodes.append(
            {
                "id": node_id,
                "phase": step.phase,
                "kernel_refs": list(step.kernel_refs),
                "obligation_refs": list(step.obligation_refs),
                "inputs": list(step.input_refs),
                "outputs": list(step.output_refs),
                "entry_gates": list(step.entry_gates),
                "exit_gates": list(step.exit_gates),
                "evidence_requirements": list(step.evidence_requirements),
                "failure_routes": list(step.failure_routes),
                "status": "planned",
                "disposition": CONVERGED if is_terminal else None,
            }
        )

    for idx in range(1, len(ordered_ids)):
        edges.append(
            {
                "from": ordered_ids[idx - 1],
                "to": ordered_ids[idx],
                "reason": "step_order",
            }
        )

    _assert_acyclic(nodes, edges)
    order = topological_order(nodes, edges)
    if order != ordered_ids:
        raise InvalidValueError(
            "topological order diverged from step order",
            path="execution_steps",
            details={"expected": ordered_ids, "got": order},
        )

    # Validation gates derive from the contract; no implicit default is fabricated.
    gates = list(contract.validation_requirements)
    # INV-003: the graph IR carries the required pending obligation ids.
    obligation_refs = [
        obligation.obligation_id
        for obligation in contract.obligations
        if obligation.required and obligation.disposition.value == "PENDING"
    ]
    terminal_disposition = CONVERGED if any(s.phase == terminal_phase for s in steps) else None
    return ExecutionGraph.from_mapping(
        {
            "graph_id": f"graph.{contract.contract_id}",
            "source_contract": contract.contract_id,
            "nodes": nodes,
            "edges": edges,
            "terminal_node": ordered_ids[-1],
            "validation_gates": gates,
            "obligation_refs": obligation_refs,
            "terminal_disposition": terminal_disposition,
        }
    )


def topological_order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    ids = [n["id"] for n in nodes]
    incoming: dict[str, set[str]] = {i: set() for i in ids}
    outgoing: dict[str, set[str]] = {i: set() for i in ids}
    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        if frm not in incoming or to not in incoming:
            raise InvalidValueError(
                "edge references missing node",
                path="edges",
                details=edge,
            )
        outgoing[frm].add(to)
        incoming[to].add(frm)
    ready = deque(sorted(i for i in ids if not incoming[i]))
    ordered: list[str] = []
    while ready:
        node = ready.popleft()
        ordered.append(node)
        for nxt in sorted(outgoing[node]):
            incoming[nxt].discard(node)
            if not incoming[nxt]:
                ready.append(nxt)
    if len(ordered) != len(ids):
        raise InvalidValueError("cycle detected in execution graph", path="edges")
    return ordered


def _assert_acyclic(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    topological_order(nodes, edges)


def assert_dependencies_satisfied(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    ids = {n["id"] for n in nodes}
    for edge in edges:
        if edge["from"] not in ids or edge["to"] not in ids:
            raise InvalidValueError(
                "missing dependency endpoint",
                path="edges",
                details=edge,
            )
