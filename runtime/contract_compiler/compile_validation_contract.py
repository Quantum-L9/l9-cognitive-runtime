#!/usr/bin/env python3
"""Validation-contract compiler CLI — thin wrapper over the typed compiler spine.

All semantic compilation lives in
``l9_cognitive_runtime.compiler.validation.ValidationContractCompiler``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parents[2]
if str(ROOT_DEFAULT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "src"))

import yaml  # noqa: E402

from l9_cognitive_runtime.compiler.context import compile_from_root  # noqa: E402

CANONICAL_MISSION = "compile the l9 cognitive runtime kernel pack"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(ROOT_DEFAULT))
    p.add_argument("--out", default="VALIDATION_CONTRACT.yaml")
    args = p.parse_args()
    root = Path(args.root)
    contracts = compile_from_root(root, CANONICAL_MISSION)
    out = root / args.out
    out.write_text(
        yaml.safe_dump(contracts.validation.to_canonical_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
