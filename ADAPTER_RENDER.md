# Adapter Render

Select the target adapter in `runtime/contract_compiler/adapters/` and render from `FINAL_EXECUTION_CONTRACT.yaml`. This file is a placeholder-free routing note, not a fake rendered prompt.

## Deterministic Renderer Roadmap

A future adapter renderer should be a small deterministic module that reads `FINAL_EXECUTION_CONTRACT.yaml` plus `EXECUTION_GRAPH.json` and emits a target-specific artifact.

Deterministic in-memory renderers live in `src/l9_cognitive_runtime/adapters/` and are exposed via the read-only MCP tool `runtime_render` (scope `runtime:render`).

Renderers serialize. They do not plan, schedule, select kernels, validate by assertion, or alter terminal doctrine.
