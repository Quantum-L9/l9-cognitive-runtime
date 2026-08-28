#!/usr/bin/env python3
"""Kernel activation planner CLI — thin wrapper over the typed compiler spine.

All routing, phase ordering, terminal gating, and kernel selection live in
``l9_cognitive_runtime.compiler.activation.ActivationPlanner``; this script
only adapts a raw task string into a typed intent, delegates, and emits
KERNEL_ACTIVATION_PLAN.yaml content. It does not execute kernels.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from l9_cognitive_runtime.compiler import ActivationPlanner, ObjectiveDeriver  # noqa: E402
from l9_cognitive_runtime.types import CompileRequest  # noqa: E402

PIPELINE_PATH = ROOT / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml"
RULES_PATH = ROOT / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml"


def build_plan(task: str, include_terminal: bool = False) -> dict[str, Any]:
    """Build an activation plan for a task (thin delegation to the typed planner)."""
    intent = ObjectiveDeriver().derive(
        CompileRequest(
            mission=task,
            source_context={"pack": "l9_cognitive_runtime_kernel_pack_clean"},
        )
    )
    plan = ActivationPlanner().plan(
        intent,
        rules_path=RULES_PATH,
        pipeline_path=PIPELINE_PATH,
        include_terminal=include_terminal,
    )
    return plan.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a kernel activation plan.")
    parser.add_argument("task", help="Task or objective to route.")
    parser.add_argument(
        "--terminal",
        action="store_true",
        help="Allow terminal Flawless Victory when route supports it.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path for KERNEL_ACTIVATION_PLAN.yaml",
    )
    args = parser.parse_args()
    plan = build_plan(args.task, include_terminal=args.terminal)
    text = yaml.safe_dump(plan, sort_keys=False, allow_unicode=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 1 if plan["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
