#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.graph import validate_execution_graph_mapping  # noqa: E402
from l9_cognitive_runtime.parsing import confined_input_file  # noqa: E402


def validate(graph: dict[str, Any]) -> list[str]:
    """Compatibility projection over the canonical graph validator."""
    return validate_execution_graph_mapping(graph)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph")
    parser.add_argument(
        "--root",
        default=str(Path.cwd()),
        help="Directory the graph input must remain beneath (default: cwd)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    graph_path = confined_input_file(args.graph, allow_root=Path(args.root))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    findings = validate(graph)
    status = "passed" if not findings else "failed"
    out = {"validator": "graph_validator.py", "status": status, "findings": findings}
    print(json.dumps(out, indent=2, sort_keys=True) if args.json else out)
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
