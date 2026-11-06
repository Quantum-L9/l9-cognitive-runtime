#!/usr/bin/env python3
# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.runtime_kernel_pipeline_validators_validate_contract_compiler__py
# title: validate contract compiler
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: runtime/kernel_pipeline/validators/validate_contract_compiler.py
# content_hash: 633ce8aba3b6b108c2252e2b30b229e1aecac6edf9c7d57ff4baf22f56e4fd64
# token_cost_estimate: 390
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED = [
 'contracts/execution_contract.schema.json',
 'contracts/validation_contract.schema.json',
 'contracts/handoff_contract.schema.json',
 'contracts/adapter_render.schema.json',
 'runtime/contract_compiler/compile_execution_contract.py',
 'runtime/contract_compiler/compile_validation_contract.py',
 'runtime/contract_compiler/compile_handoff_contract.py',
 'runtime/contract_compiler/adapters/claude_code.md',
 'runtime/contract_compiler/adapters/cursor.md',
 'runtime/contract_compiler/adapters/codex.md',
 'runtime/contract_compiler/adapters/chatgpt.md',
 'runtime/contract_compiler/adapters/human_operator.md',
]

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--root', required=True); p.add_argument('--json', action='store_true'); args=p.parse_args()
    root=Path(args.root)
    findings=[]
    for rel in REQUIRED:
        if not (root/rel).exists(): findings.append(f'missing {rel}')
    fv=(root/'runtime/kernels/terminal/flawless_victory.contract.yaml').exists()
    if not fv: findings.append('missing terminal doctrine runtime/kernels/terminal/flawless_victory.contract.yaml')
    status='passed' if not findings else 'failed'
    out={'validator':'validate_contract_compiler.py','status':status,'findings':findings,'checked_files':REQUIRED}
    print(json.dumps(out, indent=2, sort_keys=True) if args.json else out)
    return 0 if status=='passed' else 1
if __name__=='__main__': raise SystemExit(main())
