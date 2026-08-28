#!/usr/bin/env python3
"""Execution-graph builder CLI — thin wrapper over the package graph compiler.

All graph semantics live in ``l9_cognitive_runtime.graph.derive_execution_graph``.
This script only loads an execution contract and serializes the derived graph.
The former hard-coded DEFAULT_PHASES graph is removed: a graph is always a
deterministic projection of a validated execution contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.cli import confined_output_path  # noqa: E402
from l9_cognitive_runtime.graph import derive_execution_graph  # noqa: E402
from l9_cognitive_runtime.models import ExecutionContract  # noqa: E402
from l9_cognitive_runtime.parsing import load_yaml_file  # noqa: E402


def build(source_contract: str, root: Path | None = None) -> dict[str, Any]:
    """Derive the execution graph for a contract file (thin delegation)."""
    base = (root or ROOT).resolve()
    contract = ExecutionContract.from_mapping(load_yaml_file(base / source_contract))
    return derive_execution_graph(contract).to_canonical_dict()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-contract", default="FINAL_EXECUTION_CONTRACT.yaml")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--output", default="EXECUTION_GRAPH.json")
    p.add_argument(
        "--allow-write-root",
        default=None,
        help="Directory --output must stay beneath (default: cwd)",
    )
    args = p.parse_args()
    graph = build(args.source_contract, Path(args.root))
    write_root = Path(args.allow_write_root) if args.allow_write_root else None
    out = confined_output_path(args.output, allow_root=write_root)
    out.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
