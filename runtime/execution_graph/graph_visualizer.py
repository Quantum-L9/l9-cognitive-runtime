#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('graph'); p.add_argument('--output', default='EXECUTION_GRAPH.md'); args=p.parse_args()
    graph=json.loads(Path(args.graph).read_text())
    lines=['# Execution Graph','']
    for n in graph['nodes']:
        lines.append(f"- `{n['id']}`: {n['phase']} -> {', '.join(n['outputs'])}")
    lines.append('')
    lines.append('## Edges')
    for e in graph['edges']: lines.append(f"- `{e['from']}` -> `{e['to']}` ({e.get('reason','')})")
    Path(args.output).write_text('\n'.join(lines)+'\n')
    print(args.output)
    return 0
if __name__=='__main__': raise SystemExit(main())
