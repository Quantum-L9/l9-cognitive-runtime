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
