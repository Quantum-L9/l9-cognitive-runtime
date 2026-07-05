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
    p=argparse.ArgumentParser(); p.add_argument('--root', default=str(ROOT_DEFAULT)); p.add_argument('--out', default='HANDOFF_CONTRACT.yaml'); args=p.parse_args()
    root=Path(args.root)
    manifest=json.loads(read_text(root/'MANIFEST.json')) if (root/'MANIFEST.json').exists() else {}
    contract={'contract_id':'HANDOFF_CONTRACT','contract_type':'handoff_contract','handoff_summary':'Clean L9 Cognitive Runtime kernel pack with validator, planner, and universal contract compiler layers.','loaded_context':['runtime/kernels','runtime/kernel_pipeline','runtime/kernel_pipeline/planner','runtime/contract_compiler','contracts'],'decisions':['Flawless Victory is terminal doctrine, not Claude-specific format.','Canonical contracts compile before adapter-specific renders.','Adapters render execution intent without owning runtime law.'],'unknowns':manifest.get('remaining_unknowns',[]),'next_action':'Render the universal execution contract through the adapter matching the target environment.','adapter_notes':{'claude_code':'repo execution prompt','cursor':'workspace task packet','codex':'dev-kit execution prompt','chatgpt':'handoff/task prompt','human_operator':'runbook checklist'}}
    write_yaml_like(root/args.out, contract); print(root/args.out); return 0
if __name__=='__main__': raise SystemExit(main())
