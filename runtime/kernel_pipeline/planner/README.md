---
id: "l9-cognitive-runtime.context.runtime_kernel_pipeline_planner_readme__md"
title: "README"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "runtime/kernel_pipeline/planner/README.md"
content_hash: "1272921b45763a4bf6762af89fac4d764a972bc6066bc35a80d7bca0229fc78d"
token_cost_estimate: 240
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "compiler"
description: "Unknown"
activation_signals: ["build", "kernel", "route", "contract"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
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
