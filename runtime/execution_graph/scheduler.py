#!/usr/bin/env python3
from __future__ import annotations
from dependency_resolver import topological_order

def schedule(graph: dict) -> list[dict]:
    order=topological_order(graph['nodes'], graph['edges'])
    by_id={n['id']:n for n in graph['nodes']}
    return [by_id[i] for i in order]
