#!/usr/bin/env python3
# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.runtime_execution_graph_dependency_resolver__py
# title: dependency resolver
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: runtime/execution_graph/dependency_resolver.py
# content_hash: d8ffd11bf732cc0f7f92a13f2e8bb6b9ecd3bec952fdd1f631ec28ad2403276d
# token_cost_estimate: 174
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
from __future__ import annotations

def topological_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    ids=[n['id'] for n in nodes]
    incoming={i:set() for i in ids}
    outgoing={i:set() for i in ids}
    for e in edges:
        outgoing[e['from']].add(e['to'])
        incoming[e['to']].add(e['from'])
    ready=[i for i in ids if not incoming[i]]
    ordered=[]
    while ready:
        n=ready.pop(0); ordered.append(n)
        for m in sorted(outgoing[n]):
            incoming[m].discard(n)
            if not incoming[m]: ready.append(m)
    if len(ordered)!=len(ids):
        raise ValueError('cycle detected in execution graph')
    return ordered
