# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_integration_test_graph_semantics__py
# title: test graph semantics
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/integration/test_graph_semantics.py
# content_hash: c169f3672d6e2383d28b3bd75a69de0f8054a605b61f94ef96933189d9128386
# token_cost_estimate: 360
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Integration-scope graph semantics: structured steps, obligations in nodes,
kernel refs from the contract, terminal dispositions."""

from __future__ import annotations

from pathlib import Path

from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def test_graph_nodes_carry_obligations_and_gates(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    required = {o.obligation_id for o in bundle.execution.obligations if o.required}
    realized = {ref for node in bundle.graph.nodes for ref in node.obligation_refs}
    assert required <= realized
    declared = set(bundle.execution.kernel_activation)
    invoked = {ref for node in bundle.graph.nodes for ref in node.kernel_refs}
    assert declared == invoked
    for node in bundle.graph.nodes:
        assert node.failure_routes
        assert node.exit_gates or node.id == bundle.graph.terminal_node
        assert node.evidence_requirements or node.kernel_refs


def test_graph_terminal_disposition_absent_without_terminal_phase(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    assert bundle.graph.terminal_disposition is None
    assert all(node.disposition is None for node in bundle.graph.nodes)
