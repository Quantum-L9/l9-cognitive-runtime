#!/usr/bin/env python3
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
