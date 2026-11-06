#!/usr/bin/env python3
# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.runtime_execution_graph_scheduler__py
# title: scheduler
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: runtime/execution_graph/scheduler.py
# content_hash: df0a49171d8d63d6e226227059f33ea7224f0c206f4d02ecc55f71aac3659581
# token_cost_estimate: 74
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
from __future__ import annotations
from dependency_resolver import topological_order

def schedule(graph: dict) -> list[dict]:
    order=topological_order(graph['nodes'], graph['edges'])
    by_id={n['id']:n for n in graph['nodes']}
    return [by_id[i] for i in order]
