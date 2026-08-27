#!/usr/bin/env python3
"""Intent-contract compiler CLI — thin wrapper over the typed objective deriver.

All intent derivation lives in
``l9_cognitive_runtime.compiler.objective.ObjectiveDeriver``; this script only
adapts CLI arguments into a ``CompileRequest`` and serializes the canonical
intent contract.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from l9_cognitive_runtime.compiler import ObjectiveDeriver  # noqa: E402
from l9_cognitive_runtime.types import CompileRequest  # noqa: E402

DEFAULT_TASK_TYPE = "kernel_runtime_convergence"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mission", required=True)
    p.add_argument("--task-type", default=DEFAULT_TASK_TYPE)
    p.add_argument("--output", default="INTENT_CONTRACT.yaml")
    args = p.parse_args()
    intent = ObjectiveDeriver().derive(
        CompileRequest(
            mission=args.mission,
            task_type=args.task_type,
            source_context={"pack": "l9_cognitive_runtime_kernel_pack_clean"},
        )
    )
    Path(args.output).write_text(
        yaml.safe_dump(intent.to_canonical_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
