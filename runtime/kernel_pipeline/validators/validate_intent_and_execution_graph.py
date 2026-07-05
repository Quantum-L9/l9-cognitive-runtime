#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

REQUIRED=[
 'contracts/intent_contract.schema.json',
 'runtime/intent_compiler/README.md',
 'runtime/intent_compiler/INTENT_COMPILER.yaml',
 'runtime/intent_compiler/compile_intent_contract.py',
 'runtime/execution_graph/README.md',
 'runtime/execution_graph/graph.schema.json',
 'runtime/execution_graph/build_execution_graph.py',
 'runtime/execution_graph/graph_validator.py',
 'runtime/execution_graph/dependency_resolver.py',
 'runtime/execution_graph/scheduler.py',
 'runtime/execution_graph/graph_visualizer.py',
 'EXECUTION_GRAPH.json',
 'EXECUTION_GRAPH.md',
]

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--root', required=True); p.add_argument('--json', action='store_true'); args=p.parse_args()
    root=Path(args.root); findings=[]
    for rel in REQUIRED:
        if not (root/rel).exists(): findings.append(f'missing {rel}')
    graph=root/'EXECUTION_GRAPH.json'
    if graph.exists():
        proc=subprocess.run([sys.executable, str(root/'runtime/execution_graph/graph_validator.py'), str(graph), '--json'], capture_output=True, text=True)
        if proc.returncode!=0: findings.append('execution graph validation failed: '+proc.stdout+proc.stderr)
    status='passed' if not findings else 'failed'
    out={'validator':'validate_intent_and_execution_graph.py','status':status,'findings':findings,'checked_files':REQUIRED}
    print(json.dumps(out, indent=2, sort_keys=True) if args.json else out)
    return 0 if status=='passed' else 1
if __name__=='__main__': raise SystemExit(main())
