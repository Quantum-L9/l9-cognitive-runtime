#!/usr/bin/env python3
"""Execution-contract compiler CLI — thin wrapper over the typed compiler spine.

All semantic compilation lives in
``l9_cognitive_runtime.compiler.execution.ExecutionContractCompiler``. This
script only parses a KERNEL_ACTIVATION_PLAN.yaml into a typed plan, delegates,
and writes the compiled contract. A plan without kernels is a failure — there
is no silent default-kernel fallback.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parents[2]
if str(ROOT_DEFAULT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "src"))

import yaml  # noqa: E402

from l9_cognitive_runtime.cli import confined_output_path  # noqa: E402
from l9_cognitive_runtime.compiler import ActivationPlan  # noqa: E402
from l9_cognitive_runtime.compiler.context import compile_execution_from_plan  # noqa: E402
from l9_cognitive_runtime.models.errors import InvalidValueError  # noqa: E402
from l9_cognitive_runtime.parsing import load_yaml_file  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(ROOT_DEFAULT))
    p.add_argument("--activation-plan", required=True)
    p.add_argument("--out", default="FINAL_EXECUTION_CONTRACT.yaml")
    p.add_argument(
        "--allow-write-root",
        default=None,
        help="Directory generated inputs/outputs must stay beneath (default: --root)",
    )
    args = p.parse_args()
    root = Path(args.root).expanduser().resolve()
    io_root = (
        Path(args.allow_write_root).expanduser().resolve()
        if args.allow_write_root
        else root
    )
    requested_plan = Path(args.activation_plan).expanduser()
    plan_path = requested_plan if requested_plan.is_absolute() else root / requested_plan
    plan_data = load_yaml_file(plan_path, allow_root=io_root if requested_plan.is_absolute() else root)
    if not plan_data.get("active_kernels"):
        raise InvalidValueError(
            "activation plan has no active kernels; refusing a default kernel set",
            path=str(plan_path),
        )
    plan = ActivationPlan.from_mapping(plan_data)
    execution = compile_execution_from_plan(root, plan)
    out = confined_output_path(args.out, allow_root=io_root)
    out.write_text(
        yaml.safe_dump(execution.to_canonical_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
