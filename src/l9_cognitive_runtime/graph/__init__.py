"""Derive execution graphs from validated execution contracts.

This is a pure, deterministic transform of an ``ExecutionContract`` into an
``ExecutionGraph`` — not a runtime scheduler. Nodes derive from the contract's
declared ``execution_sequence``, edges derive from that declared order, cycles
and unresolved dependencies are rejected, and identical contracts produce
byte-identical canonical graphs.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from l9_cognitive_runtime.models import ExecutionContract, ExecutionGraph
from l9_cognitive_runtime.models.errors import InvalidValueError

# Default phase map used when the contract sequence maps 1:1 onto pack phases.
_DEFAULT_PHASE_META: dict[str, tuple[str, list[str]]] = {
    "lock context": ("front_end_intake", ["repo_auditor_kernel"]),
    "run constitutional preflight": (
        "semantic_preflight",
        ["K01", "K02", "K03", "K04", "K05"],
    ),
    "apply selected task and architecture kernels": (
        "strategic_expansion",
        ["prompt_compiler_kernel"],
    ),
    "run alignment and stub gate": ("structural_validation", ["validate_eliminate_stubs"]),
    "run recursive improvement": ("optimization", ["recursive_improvement"]),
    "run leverage compression": ("global_optimization", ["recursive_leverage"]),
    "execute terminal doctrine only after gates pass": ("emission", ["flawless_victory"]),
    "emit evidence-backed final summary": ("emission", ["flawless_victory"]),
}


def derive_execution_graph(contract: ExecutionContract) -> ExecutionGraph:
    """Build a deterministic graph from an execution contract's sequence."""
    if not contract.execution_sequence:
        raise InvalidValueError(
            "execution_sequence required to derive graph",
            path="execution_sequence",
        )

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    ordered_ids: list[str] = []

    for step in contract.execution_sequence:
        node_id, kernels = _step_to_node(step, contract)
        if node_id in seen_ids:
            # Deterministic collapse of duplicate logical steps into one node.
            continue
        seen_ids.add(node_id)
        ordered_ids.append(node_id)
        nodes.append(
            {
                "id": node_id,
                "phase": step,
                "kernel_refs": kernels,
                "outputs": [f"{node_id.upper()}.md"],
                "status": "planned",
            }
        )

    for idx in range(1, len(ordered_ids)):
        edges.append(
            {
                "from": ordered_ids[idx - 1],
                "to": ordered_ids[idx],
                "reason": "contract_sequence",
            }
        )

    _assert_acyclic(nodes, edges)
    order = topological_order(nodes, edges)
    if order != ordered_ids:
        raise InvalidValueError(
            "topological order diverged from contract sequence",
            path="execution_sequence",
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
    return ExecutionGraph.from_mapping(
        {
            "graph_id": f"graph.{contract.contract_id}",
            "source_contract": contract.contract_id,
            "nodes": nodes,
            "edges": edges,
            "terminal_node": ordered_ids[-1],
            "validation_gates": gates,
            "obligation_refs": obligation_refs,
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


def _step_to_node(step: str, contract: ExecutionContract) -> tuple[str, list[str]]:
    key = step.strip().lower()
    if key in _DEFAULT_PHASE_META:
        node_id, kernels = _DEFAULT_PHASE_META[key]
        return node_id, list(kernels)
    # Deterministic slug from the contract step text.
    slug = "".join(ch if ch.isalnum() else "_" for ch in key).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    if not slug:
        raise InvalidValueError("empty execution step", path="execution_sequence")
    kernels = list(contract.kernel_activation[:1]) if contract.kernel_activation else []
    return slug, kernels


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
