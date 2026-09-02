#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.parsing import confined_input_file  # noqa: E402

CANONICAL_OUTPUT = "EXECUTION_GRAPH.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph")
    parser.add_argument(
        "--root",
        default=str(Path.cwd()),
        help="Directory the graph input must remain beneath (default: cwd)",
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

    # Compatibility surface is intentionally canonical-only: callers may choose
    # where to run the CLI, but not an arbitrary filesystem destination.
    output = Path.cwd() / CANONICAL_OUTPUT
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
