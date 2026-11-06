---
id: "l9-cognitive-runtime.context.runtime_execution_graph_readme__md"
title: "README"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "runtime/execution_graph/README.md"
content_hash: "7f86e70774092bde2a88aae4e6014443782798eb398bc7db787603cb73cddbbd"
token_cost_estimate: 86
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "meta_kernel_forge"
description: "Unknown"
activation_signals: ["kernel"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
# Execution Graph

The execution graph is the canonical intermediate representation between universal execution contracts and adapter-specific outputs.

It captures ordered phases, kernel references, dependencies, outputs, and validation gates once, so Claude, Cursor, Codex, ChatGPT, and human renderers do not re-invent sequencing logic.

