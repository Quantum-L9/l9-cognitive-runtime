#!/usr/bin/env python3
"""Validate the kernel activation planner files and core routing behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from _common import STATUS_FAIL, STATUS_PASS, base_parser, emit, load_yaml, resolve_root


def load_planner_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("plan_activation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load planner module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = base_parser("Validate kernel activation planner.")
    args = parser.parse_args()
    root = resolve_root(__file__, args.root)
    findings: list[str] = []

    planner_dir = root / "runtime" / "kernel_pipeline" / "planner"
    required = [
        planner_dir / "TASK_ROUTING_RULES.yaml",
        planner_dir / "ACTIVATION_PLAN_SCHEMA.yaml",
        planner_dir / "plan_activation.py",
        planner_dir / "README.md",
    ]
    for path in required:
        if not path.exists():
            findings.append(f"Missing planner file: {path.relative_to(root)}")

    if not findings:
        rules = load_yaml(planner_dir / "TASK_ROUTING_RULES.yaml")
        routes = rules.get("task_routes", {})
        if len(routes) < 5:
            findings.append("Planner defines fewer than five task routes.")
        if "terminal_activation" not in rules:
            findings.append("Planner missing terminal_activation rules.")
        for route_name, route in routes.items():
            for field in ["match_any", "phases", "task_kernels"]:
                if field not in route:
                    findings.append(f"Route {route_name} missing {field}.")
            if "P2_TASK_ROUTING" not in route.get("phases", []):
                findings.append(f"Route {route_name} does not include P2_TASK_ROUTING.")

        try:
            planner = load_planner_module(planner_dir / "plan_activation.py")
            plan = planner.build_plan("clean and dedupe this L9 kernel pack", include_terminal=False)
            if plan["matched_route"] != "cleanup_streamline":
                findings.append("Planner did not route cleanup/dedupe task to cleanup_streamline.")
            if "P7_FLAWLESS_VICTORY" in plan["phase_sequence"]:
                findings.append("Planner activated Flawless Victory without terminal flag.")
            if len(plan["active_kernels"]) != len(set(plan["active_kernels"])):
                findings.append("Planner emitted duplicate active kernels.")
            terminal_plan = planner.build_plan("make final execution-ready build contract with flawless victory", include_terminal=True)
            if "P7_FLAWLESS_VICTORY" not in terminal_plan["phase_sequence"]:
                findings.append("Planner failed to include terminal phase when terminal flag was supplied.")
        except Exception as exc:
            findings.append(f"Planner execution failed: {exc}")

    result = {
        "validator": "validate_activation_planner.py",
        "status": STATUS_FAIL if findings else STATUS_PASS,
        "findings": findings,
    }
    return emit(result, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
