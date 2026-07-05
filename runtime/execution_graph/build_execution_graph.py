#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

DEFAULT_PHASES=[
    ('front_end_intake','Phase 0 Front-End / Intent Intake',['repo_auditor_kernel']),
    ('semantic_preflight','Phase 1 Semantic Analysis / Constitutional Preflight',['K01','K02','K03','K04','K05']),
    ('strategic_expansion','Phase 2 Strategic Expansion',['prompt_compiler_kernel']),
    ('architecture_synthesis','Phase 3 Architecture Synthesis',['l9_engine_build_kernel']),
    ('structural_validation','Phase 4 Structural Validation',['validate_eliminate_stubs']),
    ('optimization','Phase 5 Optimization',['recursive_improvement']),
    ('global_optimization','Phase 6 Global Optimization',['recursive_leverage']),
    ('emission','Phase 7 Emission',['flawless_victory']),
]

def build(source_contract: str) -> dict:
    nodes=[]; edges=[]
    for idx,(node_id,phase,kernels) in enumerate(DEFAULT_PHASES):
        nodes.append({'id':node_id,'phase':phase,'kernel_refs':kernels,'outputs':[node_id.upper()+'.md'],'status':'planned'})
        if idx>0: edges.append({'from':DEFAULT_PHASES[idx-1][0],'to':node_id,'reason':'phase_order'})
    return {
        'graph_id':'l9_execution_graph.v1',
        'source_contract':source_contract,
        'nodes':nodes,
        'edges':edges,
        'terminal_node':'emission',
        'validation_gates':['pipeline_order','kernel_roles','no_duplicate_active_kernels','phase_outputs','contract_compiler','execution_graph'],
    }

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--source-contract', default='FINAL_EXECUTION_CONTRACT.yaml'); p.add_argument('--output', default='EXECUTION_GRAPH.json'); args=p.parse_args()
    graph=build(args.source_contract)
    Path(args.output).write_text(json.dumps(graph, indent=2, sort_keys=True)+"\n")
    print(args.output)
    return 0
if __name__=='__main__': raise SystemExit(main())
