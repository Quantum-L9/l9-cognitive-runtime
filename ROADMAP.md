# Roadmap

## Current Convergence Baseline

The active pack is v5: Intent Compiler + Execution Graph convergence.

Canonical path:

```text
Human Intent -> Intent Compiler -> Kernel Planner -> Universal Execution Contract -> Execution Graph -> Validation -> Adapter Render
```

## Next Roadmap Gate: Deterministic Adapter Renderers

A real adapter renderer is a small deterministic module that serializes canonical runtime artifacts into a target execution surface.

It is not a new planning brain, orchestration engine, strategy layer, or AI agent.

### Target Renderer Shape

```text
runtime/contract_compiler/renderers/
├── render_claude_code.py
├── render_cursor.py
├── render_codex.py
├── render_chatgpt.py
└── render_human_operator.py
```

### Inputs

```text
FINAL_EXECUTION_CONTRACT.yaml
EXECUTION_GRAPH.json
ADAPTER_RENDER.md
```

### Outputs

```text
dist/claude_code_prompt.md
dist/cursor_task.md
dist/codex_prompt.md
dist/chatgpt_handoff.md
dist/human_runbook.md
```

### Renderer Boundary

Renderers may:

- map canonical phases to target-platform sections
- preserve execution order from the graph
- preserve validation requirements
- preserve stop conditions
- preserve evidence requirements
- emit platform-specific formatting

Renderers must not:

- choose kernels
- rewrite execution order
- invent validation
- activate Flawless Victory early
- change task strategy
- resolve Unknowns as facts
- duplicate planner, scheduler, or validator logic

## Stability Requirement Before Building Renderers

Do not promote adapter renderers from templates to deterministic modules until the canonical contract and execution graph are stable across 2-3 real use cases.

Required proof:

1. The same `FINAL_EXECUTION_CONTRACT.yaml` schema handles each use case without schema surgery.
2. The same `EXECUTION_GRAPH.json` schema handles sequencing, dependencies, validation, and terminal doctrine without structure changes.
3. Kernel planning changes only data values, not compiler architecture.
4. Validation remains honest: `passed`, `failed`, `blocked`, or `not_run` with reasons.
5. Adapter output differences are serialization differences only, not logic differences.

## Candidate Use Cases For Stability Testing

Use case 1: Kernel pack cleanup / dedupe / convergence.

Use case 2: Repo audit -> implementation contract -> validation evidence.

Use case 3: Handoff pack -> execution graph -> human/Codex/Claude render.

## Promotion Rule

Only after 2-3 real use cases pass without canonical IR changes should the pack add deterministic adapter renderer scripts.

Until then, adapter files remain templates and documentation, not executable emitters.

## Convergence Principle

Stabilize the intermediate representations before multiplying output surfaces.

That keeps the runtime model-agnostic and prevents five adapters from becoming five subtly different runtimes.
