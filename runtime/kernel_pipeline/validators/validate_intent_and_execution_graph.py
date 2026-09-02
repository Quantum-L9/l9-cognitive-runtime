#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.graph import validate_execution_graph_mapping  # noqa: E402
from l9_cognitive_runtime.models.errors import InvalidValueError  # noqa: E402
from l9_cognitive_runtime.parsing import confined_input_file  # noqa: E402

REQUIRED = [
    "contracts/intent_contract.schema.json",
    "runtime/intent_compiler/README.md",
    "runtime/intent_compiler/INTENT_COMPILER.yaml",
    "runtime/intent_compiler/compile_intent_contract.py",
    "runtime/execution_graph/README.md",
    "runtime/execution_graph/graph.schema.json",
    "runtime/execution_graph/build_execution_graph.py",
    "runtime/execution_graph/graph_validator.py",
    "runtime/execution_graph/dependency_resolver.py",
    "runtime/execution_graph/scheduler.py",
    "runtime/execution_graph/graph_visualizer.py",
    "EXECUTION_GRAPH.json",
    "EXECUTION_GRAPH.md",
]


def _validated_root(raw: str) -> Path:
    candidate = Path(raw).expanduser().resolve()
    canonical = ROOT.resolve()
    try:
        candidate.relative_to(canonical)
    except ValueError as exc:
        raise InvalidValueError(
            "validator root escapes repository",
            path=raw,
            details={"repository_root": str(canonical), "resolved": str(candidate)},
        ) from exc
    if not candidate.is_dir():
        raise InvalidValueError("validator root is not a directory", path=str(candidate))
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = _validated_root(args.root)
    findings: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).exists():
            findings.append(f"missing {rel}")

    graph_candidate = root / "EXECUTION_GRAPH.json"
    if graph_candidate.exists():
        graph_path = confined_input_file(graph_candidate, allow_root=root)
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(f"execution graph is not valid JSON: {exc}")
        else:
            if not isinstance(graph, dict):
                findings.append("execution graph root must be an object")
            else:
                graph_findings = validate_execution_graph_mapping(graph)
                findings.extend(
                    f"execution graph validation failed: {finding}" for finding in graph_findings
                )

    status = "passed" if not findings else "failed"
    out = {
        "validator": "validate_intent_and_execution_graph.py",
        "status": status,
        "findings": findings,
        "checked_files": REQUIRED,
    }
    print(json.dumps(out, indent=2, sort_keys=True) if args.json else out)
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
