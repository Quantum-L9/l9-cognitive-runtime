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
    p=argparse.ArgumentParser(); p.add_argument('--root', default=str(ROOT_DEFAULT)); p.add_argument('--out', default='VALIDATION_CONTRACT.yaml'); args=p.parse_args()
    root=Path(args.root)
    contract={'contract_id':'VALIDATION_CONTRACT','contract_type':'validation_contract','validation_ladder':['format','schema','pipeline_order','kernel_roles','duplicate_active_kernel_scan','activation_planner','contract_compiler','adapter_render','evidence_manifest'],'evidence_required':['command run or blocker reason','validator name','status','findings','timestamp or report path'],'allowed_statuses':['passed','failed','blocked','not_run','unknown','not_applicable_with_reason'],'report_outputs':['runtime/kernel_pipeline/KERNEL_PIPELINE_VALIDATION_REPORT.json','VALIDATION_EVIDENCE.md']}
    write_yaml_like(root/args.out, contract); print(root/args.out); return 0
if __name__=='__main__': raise SystemExit(main())
