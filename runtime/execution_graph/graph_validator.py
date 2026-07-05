#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from dependency_resolver import topological_order

def validate(graph: dict) -> list[str]:
    findings=[]
    ids=[n.get('id') for n in graph.get('nodes',[])]
    if len(ids)!=len(set(ids)): findings.append('duplicate node id')
    if graph.get('terminal_node') not in ids: findings.append('terminal_node missing from nodes')
    edge_ids={(e.get('from'),e.get('to')) for e in graph.get('edges',[])}
    for a,b in edge_ids:
        if a not in ids or b not in ids: findings.append(f'edge references missing node: {a}->{b}')
    try: topological_order(graph.get('nodes',[]), graph.get('edges',[]))
    except Exception as e: findings.append(str(e))
    return findings

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('graph'); p.add_argument('--json', action='store_true'); args=p.parse_args()
    graph=json.loads(Path(args.graph).read_text())
    findings=validate(graph); status='passed' if not findings else 'failed'
    out={'validator':'graph_validator.py','status':status,'findings':findings}
    print(json.dumps(out, indent=2, sort_keys=True) if args.json else out)
    return 0 if status=='passed' else 1
if __name__=='__main__': raise SystemExit(main())
