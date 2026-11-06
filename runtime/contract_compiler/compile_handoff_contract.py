#!/usr/bin/env python3
# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.runtime_contract_compiler_compile_handoff_contract__py
# title: compile handoff contract
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: runtime/contract_compiler/compile_handoff_contract.py
# content_hash: f372717a5035891629274761726d60d6ac7238adfe58f78b6b488fc5ccc4f7ee
# token_cost_estimate: 377
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Handoff-contract compiler CLI — thin wrapper over the typed compiler spine.

All semantic compilation lives in
``l9_cognitive_runtime.compiler.handoff.HandoffContractCompiler``.
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
from l9_cognitive_runtime.compiler.context import compile_from_root  # noqa: E402

CANONICAL_MISSION = "compile the l9 cognitive runtime kernel pack"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(ROOT_DEFAULT))
    p.add_argument("--out", default="HANDOFF_CONTRACT.yaml")
    p.add_argument(
        "--allow-write-root",
        default=None,
        help="Directory --out must stay beneath (default: --root)",
    )
    args = p.parse_args()
    root = Path(args.root)
    write_root = Path(args.allow_write_root) if args.allow_write_root else root
    contracts = compile_from_root(root, CANONICAL_MISSION)
    out = confined_output_path(args.out, allow_root=write_root)
    out.write_text(
        yaml.safe_dump(contracts.handoff.to_canonical_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
