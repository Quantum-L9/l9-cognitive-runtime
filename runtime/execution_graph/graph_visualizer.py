#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.cli import confined_output_path  # noqa: E402
from l9_cognitive_runtime.parsing import confined_input_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph")
    parser.add_argument("--output", default="EXECUTION_GRAPH.md")
    parser.add_argument(
        "--root",
        default=str(Path.cwd()),
        help="Directory the graph input must remain beneath (default: cwd)",
    )
    parser.add_argument(
        "--allow-write-root",
        default=None,
        help="Directory --output must stay beneath (default: cwd)",
    )
    args = parser.parse_args()

    graph_path = confined_input_file(args.graph, allow_root=Path(args.root))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    lines = ["# Execution Graph", ""]
    for node in graph["nodes"]:
        lines.append(f"- `{node['id']}`: {node['phase']} -> {', '.join(node['outputs'])}")
    lines.append("")
    lines.append("## Edges")
    for edge in graph["edges"]:
        lines.append(f"- `{edge['from']}` -> `{edge['to']}` ({edge.get('reason', '')})")

    write_root = Path(args.allow_write_root) if args.allow_write_root else None
    output = confined_output_path(args.output, allow_root=write_root)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
