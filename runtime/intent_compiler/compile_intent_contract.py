#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

def emit_yaml(data: dict) -> str:
    lines=[]
    for k,v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v: lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for dk,dv in v.items(): lines.append(f"  {dk}: {dv}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)+"\n"

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--mission', required=True)
    p.add_argument('--task-type', default='kernel_runtime_convergence')
    p.add_argument('--output', default='INTENT_CONTRACT.yaml')
    args=p.parse_args()
    contract={
        'intent_id':'intent.runtime_convergence.v1',
        'mission':args.mission,
        'task_type':args.task_type,
        'constraints':['model_agnostic','kernel_first','evidence_backed','no_fake_validation'],
        'desired_outputs':['kernel_activation_plan','execution_contract','execution_graph','validation_evidence','adapter_render'],
        'source_context':{'pack':'l9_cognitive_runtime_kernel_pack_clean'},
        'unknowns':[]
    }
    Path(args.output).write_text(emit_yaml(contract))
    print(args.output)
    return 0
if __name__ == '__main__': raise SystemExit(main())
