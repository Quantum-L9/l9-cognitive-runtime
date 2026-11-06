#!/usr/bin/env python3
# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.runtime_kernel_pipeline_run_validators__py
# title: run validators
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: runtime/kernel_pipeline/run_validators.py
# content_hash: 6a9a7600cbd1769ca67cc840009333d7a70b74032f18d6417d0f24a7baba1368
# token_cost_estimate: 354
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Run every clean kernel-pack validator and emit one JSON report."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_DIR = Path(__file__).resolve().parent / "validators"
VALIDATORS = [
    "validate_pipeline_order.py",
    "validate_kernel_roles.py",
    "validate_no_duplicate_active_kernels.py",
    "validate_phase_outputs.py",
    "validate_activation_planner.py",
    "validate_contract_compiler.py",
    "validate_intent_and_execution_graph.py",
]


def main() -> int:
    results = []
    failed = False
    for name in VALIDATORS:
        path = VALIDATOR_DIR / name
        proc = subprocess.run([sys.executable, str(path), "--root", str(ROOT), "--json"], capture_output=True, text=True)
        try:
            result = json.loads(proc.stdout)
        except Exception:
            result = {"validator": name, "status": "failed", "findings": [proc.stdout, proc.stderr]}
        result["returncode"] = proc.returncode
        results.append(result)
        failed = failed or proc.returncode != 0
    report = {"pack": "l9_cognitive_runtime_kernel_pack_clean", "status": "failed" if failed else "passed", "validators": results}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
