---
name: compile-runtime-bundle
description: Compile a plan-bound, provenance-checked L9 runtime bundle for a mission through the connected read-only L9 Cognitive Runtime MCP server. Use when the user asks to compile, plan, or validate an L9 cognitive runtime bundle, kernel activation plan, context plan, or execution packet. Requires the l9-cognitive-runtime MCP server to be connected; refuses rather than inventing tool results, context, or provenance.
license: Proprietary
compatibility: Requires a connected l9-cognitive-runtime MCP server (local stdio or an operator-registered hosted endpoint) bound to a verified runtime pack.
---

# Compile a runtime bundle with the L9 Cognitive Runtime

This skill is workflow guidance only. The connected MCP server is the sole tool
provider and the runtime is the sole compiler. Never simulate, paraphrase, or
reconstruct a tool result.

## Preconditions — fail closed

Stop and tell the user what is missing, without producing a bundle, when any of
these holds:

- No MCP server named `l9-cognitive-runtime` is connected, or its tools are not
  listed in this session. Say: "The L9 Cognitive Runtime MCP server is not
  connected." Do not guess tool output.
- `runtime_capabilities()` fails, or reports anything other than
  `mode: read_only`, `writes: false`, `execution: false`, `shell: false`.
- A tool returns an error. Report the error text verbatim and stop; never retry
  with altered inputs to obtain a success. The single exception is the
  documented `replan required` error from `compile_runtime`, handled in workflow
  step 4.
- A governed `ContextSnapshot` is needed but none was supplied by an
  authoritative source. Ask for it; never author governed context yourself.

The server is read-only. It does not execute graphs, run shell commands, write
files, or touch repositories. Never describe a compiled bundle as executed work.

## Tools (exact names and arguments)

These are the only six tools. `?` marks an optional argument. If the host
namespaces tool names, use exactly the names `runtime_capabilities()` returns in
its `tools` list, and never call a name not in that list.

| Tool | Purpose |
|---|---|
| `runtime_capabilities()` | Server identity, read-only posture, tool list, pack `manifest_digest`. |
| `compile_intent(mission, task_type?)` | Canonical intent contract and `intent_digest`. |
| `plan_kernel_activation(mission, context_snapshot?)` | Kernel activation, execution sequence, `execution_digest`, `context_digest`. |
| `plan_context_requirements(mission, task_type?, context_snapshot?)` | Typed context demand: `context_plan`, `context_plan_id`, `context_plan_digest`. |
| `compile_runtime(mission, task_type?, context_snapshot?, expected_context_plan_id?)` | Full bundle: `digests`, `context_plan_id`, `provenance`, `execution_packet`, `run_id`, `resource_uri`. |
| `validate_runtime_bundle(mission, context_snapshot?)` | Integrity verdict: `valid` plus named `checks` and `digests`. |

`mission` must be a non-empty string. `task_type` defaults to
`kernel_runtime_convergence`; pass it only when the user names one.
`context_snapshot` is a JSON object conforming to
`contracts/context_snapshot.schema.json`; omit it entirely when no governed
context exists. Never pass an empty or placeholder object as governed context.

## Workflow

1. **Check capabilities.** Call `runtime_capabilities()`. Confirm the read-only
   posture above. Record `manifest_digest` and `tools`.
2. **Plan context.** Call `plan_context_requirements(mission, task_type?, context_snapshot?)`
   with the same `mission` and `task_type` you will compile. Record
   `context_plan_id`. Show the user `context_plan.requirement_plan` — that is what
   the runtime needs, not where to get it.
3. **Obtain governed context externally.** If the plan requires context, the user
   or an authoritative outer host must supply a `ContextSnapshot`. This skill and
   this server never acquire it. If none is available, either compile without a
   snapshot (governed-empty) and say so, or stop.
4. **Compile, bound to the plan.** Call
   `compile_runtime(mission, task_type?, context_snapshot?, expected_context_plan_id?)`
   passing `expected_context_plan_id` = the id from step 2. If the error says
   `replan required`, the supplied context changed the plan: tell the user, then
   return to step 2 once, passing that same snapshot, and compile against the
   new `context_plan_id`. Only the plan is recomputed; `mission`, `task_type`
   and the snapshot stay exactly as supplied. If the second compile fails for
   any reason, stop. Do not drop `expected_context_plan_id` to force a pass.
5. **Verify before reporting.** All of the following must hold, or report the
   bundle as unverified:
   - returned `context_plan_id` equals the step 2 `context_plan_id`;
   - `digests.manifest` equals the step 1 `manifest_digest`, and
     `provenance.manifest_digest` agrees;
   - `execution_packet.compiled_task_context_digest` equals `digests.context`;
   - every value in `digests` is non-empty.
   Optionally, only when `task_type` was not supplied, call
   `validate_runtime_bundle(mission, context_snapshot?)` with the same inputs and
   require `valid: true`. It accepts no `task_type` and always compiles the
   default, so for any other `task_type` skip it and say the check was not
   applicable.

## Reporting

Report only observed values: `run_id`, `resource_uri`, `context_plan_id`, the
`digests`, the activated kernels, and which verification checks passed. Mark
anything not returned by a tool as `Unknown`. Optional supporting views are
`compile_intent(mission, task_type?)` and `plan_kernel_activation(mission, context_snapshot?)`;
use them only when the user asks for intent or kernel routing detail.
`plan_kernel_activation` likewise accepts no `task_type`; when one was supplied,
report its output as describing the default task type, not the compiled bundle.
