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

from l9_cognitive_runtime.compiler import ActivationPlan  # noqa: E402
from l9_cognitive_runtime.compiler.context import compile_execution_from_plan  # noqa: E402
from l9_cognitive_runtime.models.errors import InvalidValueError  # noqa: E402
from l9_cognitive_runtime.parsing import load_yaml_file  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(ROOT_DEFAULT))
    p.add_argument("--activation-plan", required=True)
    p.add_argument("--out", default="FINAL_EXECUTION_CONTRACT.yaml")
    args = p.parse_args()
    root = Path(args.root)
    plan_path = (
        root / args.activation_plan
        if not Path(args.activation_plan).is_absolute()
        else Path(args.activation_plan)
    )
    plan_data = load_yaml_file(plan_path)
    if not plan_data.get("active_kernels"):
        raise InvalidValueError(
            "activation plan has no active kernels; refusing a default kernel set",
            path=str(plan_path),
        )
    plan = ActivationPlan.from_mapping(plan_data)
    execution = compile_execution_from_plan(root, plan)
    out = root / args.out
    out.write_text(
        yaml.safe_dump(execution.to_canonical_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
