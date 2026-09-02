#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.models.errors import InvalidValueError  # noqa: E402
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

    write_root = (
        Path(args.allow_write_root).expanduser().resolve()
        if args.allow_write_root
        else Path.cwd().resolve()
    )
    requested_output = Path(args.output).expanduser()
    output = (
        requested_output.resolve()
        if requested_output.is_absolute()
        else (write_root / requested_output).resolve()
    )
    try:
        output.relative_to(write_root)
    except ValueError as exc:
        raise InvalidValueError(
            "output path escapes allow_write_root",
            path=args.output,
            details={"allow_write_root": str(write_root), "resolved": str(output)},
        ) from exc

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
