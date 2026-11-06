---
id: "l9-cognitive-runtime.context.runtime_intent_compiler_readme__md"
title: "README"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "runtime/intent_compiler/README.md"
content_hash: "9fcbf702e54f863d2b54cbd473abcccb0c6cf1cd6b805be0297fcc47b4d80de0"
token_cost_estimate: 118
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
# L9 Intent Compiler

Converges human intent into a canonical runtime intent contract.

Pipeline position:

```text
Human Intent -> Intent Contract -> Kernel Activation Plan -> Universal Execution Contract -> Execution Graph -> Adapter Render
```

This layer is intentionally small. It does not execute work and does not render prompts. It normalizes mission, task type, constraints, desired outputs, known context, and unknowns so downstream stages are model-agnostic.

