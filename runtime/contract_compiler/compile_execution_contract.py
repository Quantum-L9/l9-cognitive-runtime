#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parents[2]

def read_text(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")

def simple_yaml_load(path: Path) -> dict:
    # intentionally tiny loader for this pack's simple YAML shape. Uses PyYAML if available.
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(read_text(path))
        return data or {}
    except Exception:
        text = read_text(path)
        data = {}
        current_key = None
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.lstrip().startswith('#'):
                continue
            if not line.startswith(' ') and ':' in line:
                k,v = line.split(':',1)
                current_key=k.strip()
                v=v.strip().strip('"')
                if v:
                    data[current_key]=v
                else:
                    data[current_key]=[]
            elif line.strip().startswith('-') and current_key:
                data.setdefault(current_key,[]).append(line.strip()[1:].strip().strip('"'))
        return data

def write_yaml_like(path: Path, obj: dict) -> None:
    def emit(value, indent=0):
        sp='  '*indent
        lines=[]
        if isinstance(value, dict):
            for k,v in value.items():
                if isinstance(v,(dict,list)):
                    lines.append(f"{sp}{k}:")
                    lines.extend(emit(v, indent+1))
                else:
                    sval=str(v).replace('\n','\\n')
                    lines.append(f"{sp}{k}: {json.dumps(sval) if any(c in sval for c in [':','#','{','}','[',']']) else sval}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item,(dict,list)):
                    lines.append(f"{sp}-")
                    lines.extend(emit(item, indent+1))
                else:
                    lines.append(f"{sp}- {item}")
        return lines
    path.write_text('\n'.join(emit(obj))+'\n', encoding='utf-8')

def activation_kernels(plan: dict) -> list[str]:
    for key in ('selected_kernels','active_kernels','kernels','kernel_activation'):
        val = plan.get(key)
        if isinstance(val, list): return [str(x) for x in val]
    # Fallback for nested activation_plan shape
    ap=plan.get('activation_plan')
    if isinstance(ap, dict):
        for key in ('selected_kernels','active_kernels','kernels'):
            if isinstance(ap.get(key), list): return [str(x) for x in ap[key]]
    return []


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--root', default=str(ROOT_DEFAULT))
    p.add_argument('--activation-plan', required=True)
    p.add_argument('--out', default='FINAL_EXECUTION_CONTRACT.yaml')
    args=p.parse_args()
    root=Path(args.root)
    plan_path=(root/args.activation_plan if not Path(args.activation_plan).is_absolute() else Path(args.activation_plan))
    plan=simple_yaml_load(plan_path)
    pipeline=simple_yaml_load(root/'runtime/kernel_pipeline/KERNEL_PIPELINE.yaml')
    kernels=activation_kernels(plan)
    if not kernels:
        # conservative default: required terminal-free route plus Flawless Victory doctrine reference
        kernels=[
            'runtime/kernels/constitutional/K01-platform-architecture-engine.yaml',
            'runtime/kernels/constitutional/K02-contracts-code-laws-enforcement.yaml',
            'runtime/kernels/constitutional/K03-constellation-transport-authority.yaml',
            'runtime/kernels/improvement/validate_eliminate_stubs.md',
            'runtime/kernels/improvement/recursive_improvement.md',
            'runtime/kernels/improvement/recursive_leverage.md',
            'runtime/kernels/terminal/flawless_victory.contract.yaml',
        ]
    contract={
      'contract_id':'FINAL_EXECUTION_CONTRACT',
      'contract_type':'universal_execution_contract',
      'version':'1.0.0',
      'source_activation_plan':str(plan_path.relative_to(root) if plan_path.is_relative_to(root) else plan_path),
      'terminal_doctrine':'runtime/kernels/terminal/flawless_victory.contract.yaml',
      'objective':str(plan.get('objective') or plan.get('task') or 'Execute the selected runtime task with evidence-backed validation and no drift.'),
      'authority_order':['user task','kernel activation plan','repo files','runtime pipeline contracts','tests and validation evidence','Unknown'],
      'kernel_activation':kernels,
      'execution_sequence':['lock context','run constitutional preflight','apply selected task and architecture kernels','run alignment and stub gate','run recursive improvement','run leverage compression','execute terminal doctrine only after gates pass','emit evidence-backed final summary'],
      'validation_requirements':['pipeline order validated','kernel roles unique','no duplicate active kernels','phase outputs satisfied or blocked with reason','adapter render preserves canonical contract','no fake validation'],
      'stop_conditions':['activation plan missing or invalid','required kernel unavailable','terminal doctrine requested before gates pass','validation cannot be run honestly','scope conflict requires operator decision'],
      'output_contract':['summary','files_changed_or_artifacts_created','validation_results','remaining_unknowns','merge_or_execution_readiness','minimum_safe_next_action','convergence_block'],
      'adapter_targets':['claude_code','cursor','codex','chatgpt','human_operator'],
      'metadata':{'compiled_by':'runtime/contract_compiler/compile_execution_contract.py','pipeline_id':pipeline.get('pipeline_id','unknown')}
    }
    out=root/args.out
    write_yaml_like(out, contract)
    print(out)
    return 0
if __name__=='__main__': raise SystemExit(main())
