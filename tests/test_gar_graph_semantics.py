"""PHASE-05 gate evidence: structured execution graph semantics (INV-006).

Gate coverage:

- no_graph_kernel_substitution (converted A0002);
- no_unknown_step_first_kernel_fallback (converted A0003);
- every_graph_kernel_ref_originates_from_execution_contract;
- every_required_obligation_has_graph_realization_path;
- graph_acyclic;
- graph_all_required_nodes_reachable;
- graph_no_orphan_required_output;
- terminals represent CONVERGED / BLOCKED / ABORTED dispositions (A0503).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from l9_cognitive_runtime.compiler.pipeline import CompilePipeline
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import RuntimeBundle

ROOT = Path(__file__).resolve().parents[1]
ROUTES: dict[str, dict[str, list[str]]] = yaml.safe_load(
    (ROOT / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml").read_text(
        encoding="utf-8"
    )
)["task_routes"]


def _compile(valid_pack: Path, mission: str) -> RuntimeBundle:
    return CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission=mission, pack_root=valid_pack)
    )


def test_graph_kernel_refs_originate_from_contract(valid_pack: Path) -> None:
    bundle = _compile(valid_pack, "Audit and fix this repository.")
    declared = set(bundle.execution.kernel_activation)
    for node in bundle.graph.nodes:
        for ref in node.kernel_refs:
            assert ref in declared, ref
    # And every declared kernel is invoked somewhere (liveness, INV-004).
    invoked = {ref for node in bundle.graph.nodes for ref in node.kernel_refs}
    assert declared == invoked


def test_required_obligations_have_node_realization_path(valid_pack: Path) -> None:
    bundle = _compile(valid_pack, "Audit and fix this repository.")
    required = {o.obligation_id for o in bundle.execution.obligations if o.required}
    realized = {ref for node in bundle.graph.nodes for ref in node.obligation_refs}
    assert required <= realized


@pytest.mark.parametrize("include_terminal", [False, True])
@pytest.mark.parametrize("route", sorted(ROUTES))
def test_router_plan_for_every_route_realizes_every_obligation_on_a_node(
    route: str, include_terminal: bool
) -> None:
    """RG-006b: liveness now demands a node for every required pending
    obligation; every router-produced plan must still meet it."""
    for token in ROUTES[route]["match_any"]:
        result = CompilePipeline().compile_from_root(
            ROOT, f"Representative {token} mission", include_terminal=include_terminal
        )
        if result.plan.matched_route == route:
            break
    else:
        pytest.fail(f"no match_any token routes to {route}")
    bundle = result.bundle
    required = {
        o.obligation_id
        for o in bundle.execution.obligations
        if o.required and o.disposition.value == "PENDING"
    }
    realized = {ref for node in bundle.graph.nodes for ref in node.obligation_refs}
    assert required <= realized


def test_graph_is_acyclic_and_fully_reachable(valid_pack: Path) -> None:
    for mission in ("Audit this repository.", "Audit and fix this repository."):
        bundle = _compile(valid_pack, mission)
        node_ids = [n.id for n in bundle.graph.nodes]
        edge_map = {e.from_node: e.to_node for e in bundle.graph.edges}
        assert len(node_ids) == len(set(node_ids))
        # Chain: every node but the first is reached by exactly one edge, and
        # walking from the first node visits every node (acyclic, reachable).
        visited = [node_ids[0]]
        while visited[-1] in edge_map:
            visited.append(edge_map[visited[-1]])
        assert visited == node_ids
        assert bundle.graph.terminal_node == node_ids[-1]


def test_no_orphan_required_output(valid_pack: Path) -> None:
    bundle = _compile(valid_pack, "Audit and fix this repository.")
    nodes = bundle.graph.nodes
    for idx, node in enumerate(nodes[:-1]):
        downstream_inputs = set(nodes[idx + 1].inputs)
        for output in node.outputs:
            assert output in downstream_inputs, (node.id, output)


def test_terminal_dispositions_represented(valid_pack: Path) -> None:
    # A0503: with a terminal phase the graph records CONVERGED; without one,
    # nodes carry BLOCKED/ABORTED failure routes and no convergence claim.
    bundle = _compile(valid_pack, "Audit and fix this repository.")
    assert bundle.graph.terminal_disposition is None
    for node in bundle.graph.nodes:
        assert "BLOCKED" in node.failure_routes
        assert "ABORTED" in node.failure_routes
        assert node.disposition is None

    from l9_cognitive_runtime.graph import derive_execution_graph
    from l9_cognitive_runtime.models import ExecutionContract

    steps = [
        {
            "step_id": "step.P7_FLAWLESS_VICTORY",
            "phase": "P7_FLAWLESS_VICTORY",
            "kernel_refs": ["runtime/kernels/terminal/flawless_victory.contract.yaml"],
            "obligation_refs": ["OBL.CONVERGENCE"],
            "input_refs": [],
            "output_refs": ["VALIDATION_EVIDENCE.md"],
            "entry_gates": [],
            "exit_gates": [],
            "evidence_requirements": [],
            "failure_routes": ["ABORTED"],
        }
    ]
    contract = ExecutionContract.from_mapping(
        {
            "contract_id": "C1",
            "contract_type": "universal_execution_contract",
            "source_activation_plan": "plan.yaml",
            "terminal_doctrine": "terminal.yaml",
            "objective": "x",
            "authority_order": ["user task"],
            "kernel_activation": ["runtime/kernels/terminal/flawless_victory.contract.yaml"],
            "execution_sequence": ["execute terminal doctrine only after gates pass"],
            "validation_requirements": [],
            "output_contract": ["summary"],
            "adapter_targets": ["cursor"],
            "execution_steps": steps,
        }
    )
    graph = derive_execution_graph(contract)
    assert graph.terminal_disposition == "CONVERGED"
    assert graph.nodes[0].disposition == "CONVERGED"
    assert graph.nodes[0].failure_routes == ["ABORTED"]
