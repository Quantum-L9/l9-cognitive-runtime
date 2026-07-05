# Kernel Activation Planner

Deterministic task-to-kernel router for the clean L9 Cognitive Runtime kernel pack.

## Purpose

The planner selects the smallest valid kernel set for a task. It prevents the old failure mode: loading every impressive kernel and letting overlap eat the workflow.

## Inputs

- `TASK_ROUTING_RULES.yaml`
- `runtime/kernel_pipeline/KERNEL_PIPELINE.yaml`
- task text from the operator or upstream YNP layer

## Output

- `KERNEL_ACTIVATION_PLAN.yaml`

## Example

```bash
python runtime/kernel_pipeline/planner/plan_activation.py \
  "clean and dedupe this L9 kernel pack, then prepare a build contract" \
  --terminal \
  --out KERNEL_ACTIVATION_PLAN.yaml
```

## Guarantees

- Preserves canonical phase order.
- Selects task kernels by route, not by loading all task kernels.
- Keeps Flawless Victory terminal-only.
- Emits skipped kernels so omissions are explicit.
- Emits blockers and Unknowns instead of pretending certainty.
