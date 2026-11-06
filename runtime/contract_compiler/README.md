---
id: "l9-cognitive-runtime.context.runtime_contract_compiler_readme__md"
title: "README"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "runtime/contract_compiler/README.md"
content_hash: "080079dac9e5d44a86d0ebaaef1fa0868d5b2d9c72f2a6378f9d71373a2efc09"
token_cost_estimate: 217
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "compiler"
description: "Unknown"
activation_signals: ["render", "kernel", "plan", "contract"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
# Runtime Contract Compiler

The contract compiler converts a `KERNEL_ACTIVATION_PLAN.yaml` into canonical runtime contracts before any tool-specific rendering.

Pipeline:

```text
Runtime Intent
→ Kernel Activation Plan
→ FINAL_EXECUTION_CONTRACT.yaml
→ VALIDATION_CONTRACT.yaml
→ HANDOFF_CONTRACT.yaml
→ adapter render
```

Flawless Victory is terminal doctrine inside the universal execution contract. It is not a Claude-only prompt format.

## Commands

```bash
python runtime/contract_compiler/compile_execution_contract.py --root . --activation-plan runtime/kernel_pipeline/planner/KERNEL_ACTIVATION_PLAN.example.yaml --out FINAL_EXECUTION_CONTRACT.yaml
python runtime/contract_compiler/compile_validation_contract.py --root . --out VALIDATION_CONTRACT.yaml
python runtime/contract_compiler/compile_handoff_contract.py --root . --out HANDOFF_CONTRACT.yaml
```
