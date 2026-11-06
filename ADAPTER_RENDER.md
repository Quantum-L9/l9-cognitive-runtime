---
id: "l9-cognitive-runtime.context.adapter_render__md"
title: "ADAPTER RENDER"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "ADAPTER_RENDER.md"
content_hash: "f17bd07d1c6aa2972337a240b0c481d1de49de0ee8bbaf3af2ced41cb7fc0bb5"
token_cost_estimate: 180
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "auditor"
description: "Unknown"
activation_signals: ["validate", "build", "render", "plan", "schedule", "roadmap"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
# Adapter Render

Select the target adapter in `runtime/contract_compiler/adapters/` and render from `FINAL_EXECUTION_CONTRACT.yaml`. This file is a placeholder-free routing note, not a fake rendered prompt.

## Deterministic Renderer Roadmap

A future adapter renderer should be a small deterministic module that reads `FINAL_EXECUTION_CONTRACT.yaml` plus `EXECUTION_GRAPH.json` and emits a target-specific artifact.

Do not build renderer scripts until the canonical contract and graph are stable across 2-3 real use cases. Until then, this adapter layer remains a template/documentation boundary.

Renderers serialize. They do not plan, schedule, select kernels, validate by assertion, or alter terminal doctrine.
