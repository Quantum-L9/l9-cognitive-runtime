# L9 Cognitive Runtime

**The L9 Cognitive Runtime deterministically compiles a task plus governed source context into the minimum sufficient, provenance-backed cognitive context and execution packet required to perform that task correctly.**

It is a compiler, not an agent. It does not execute the task, schedule agents, persist world state or memory, route transport, or select a provider — it produces the artifacts a capable host needs in order to do those things correctly. The canonical architecture law is [`INVARIANTS.md`](INVARIANTS.md); this README describes how to use what that law governs.

## The live spine

Exactly one authoritative path compiles a fresh mission (INV-CTX-002):

```text
CompileRequest + ContextSnapshot
  -> ObjectiveDeriver          -> IntentContract
  -> TaskScopeCompiler         -> TaskScope
  -> ContextDiscoveryCompiler  -> DiscoveryContext
  -> ActivationPlanner         -> ActivationPlan
  -> KernelResolver            -> KernelBindings
  -> ContextRequirementPlanner -> ContextRequirementPlan
  -> ContextCompiler           -> CompiledTaskContext
  -> ContextClosureValidator
  -> ObligationDeriver
  -> ExecutionContractCompiler / ValidationContractCompiler / HandoffContractCompiler
  -> ExecutionGraphCompiler
  -> ExecutionPacket
  -> BundleSemanticValidator   -> RuntimeBundle
  -> AdapterRenderer
```

`CompiledTaskContext` is the canonical context IR: task scope, relevant entities, repository state, architecture constraints, applicable law, prior decisions, dependency context, evidence, memory, selected kernels, capabilities, authority, unresolved unknowns, and provenance. Its digest is computed from the finished artifact and carried *outside* it — by `RuntimeBundle.digests()["context"]` and `ExecutionPacket.compiled_task_context_digest` — so the context never contains a digest of itself.

## Governed context is a separate input

```python
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.models.context import ContextSnapshot

service = CognitiveRuntimeService()

# No governed context: identical to an empty snapshot, and to every
# pre-context caller. This keeps working unchanged.
bundle = service.compile_runtime(CompileRequest(mission="...", pack_root=pack))

# With governed context, supplied by the host as a keyword:
bundle = service.compile_runtime(
    CompileRequest(mission="...", pack_root=pack),
    context_snapshot=ContextSnapshot(repository_state=[...], applicable_law=[...]),
)

bundle.task_context          # CompiledTaskContext
bundle.digests()["context"]  # its digest, computed externally
```

`ContextSnapshot` is deliberately **not** a `CompileRequest` field. `CompileRequest.source_context` remains caller *hints*: a hint may narrow task scope (`target_refs`, `in_scope_refs`, `excluded_refs`), but it can never establish repository truth, governing law, authority, capability availability, decision status, or evidence validity (INV-CTX-006). Anything that must affect execution semantics arrives as a typed, provenance-backed governed item.

That boundary is load-bearing. Architecture materiality, for instance, activates the Global Architect from mission tokens (the caller stating their own intent) plus governed discovery signals — a `GovernedConstraint` carrying an immutable coordinate. A raw `source_context.context_signals` list proves nothing.

## The external source boundary

The compiler defines what governed context *is* and consumes immutable snapshots of it. It does not fetch any of it. There is no GitHub crawler, no Graphiti client, no vector or database client, no network discovery inside the semantic compiler (INV-CTX-009, INV-CTX-033) — `tests/test_architecture_invariants.py` enforces that as a static property of the tree.

An outer host acquires context between phases and injects it. What the compiler does read is the verified runtime pack it already depends on: routing rules, the pipeline definition, kernels, and schemas, all manifest-bound and immutable.

**Explicit non-goals.** Observability is not a concern of this repository — no trace or span lifecycle, no telemetry export, no metrics pipeline, no `l9-observability-core` integration (INV-CTX-034). Neither is world-state or memory-store ownership (INV-CTX-035). A host may observe the runtime; the runtime returns compiler artifacts, digests, provenance, and validation semantics only.

## Development Setup (Python package baseline)

The repository is an installable Python project. The `src/l9_cognitive_runtime` package is a baseline namespace only; existing `runtime/` semantics are unchanged and are not relocated by this baseline.

```bash
# Isolated install (editable + dev tools)
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"

# Verify import
python -c "import l9_cognitive_runtime; print(l9_cognitive_runtime.__version__)"

# Tests, lint, types, build
pytest
ruff check src tests
mypy
python -m build
```

Build artifacts (`dist/`, `*.egg-info/`, caches) must not be committed.

## Canonical Tree

```text
runtime/kernels/
├── constitutional/
│   ├── K01-platform-architecture-engine.yaml
│   ├── K02-contracts-code-laws-enforcement.yaml
│   ├── K03-constellation-transport-authority.yaml
│   ├── K04-domain-spec-yaml-authoring.yaml
│   └── K05-file-ownership-placement-capability-registry.yaml
│
├── task/
│   ├── developer_core_kernel.yaml
│   ├── repo_auditor_kernel.yaml
│   ├── prompt_compiler_kernel.yaml
│   ├── l9_engine_build_kernel.yaml
│   └── code_review_ci_kernel.yaml
│
├── architecture/
│   ├── repo_taxonomy_and_dependency_architecture.md
│   ├── dependency_birth_and_mirror_codegen.md
│   └── bundle_and_node_extras.md
│
├── improvement/
│   ├── recursive_alignment.md
│   ├── validate_eliminate_stubs.md
│   ├── recursive_improvement.md
│   └── recursive_leverage.md
│
└── terminal/
    └── flawless_victory.contract.yaml
```

## Operating Pipeline

Use `runtime/kernel_pipeline/KERNEL_PIPELINE.yaml` as the source of truth.

Phase flow:

1. `P0_UNPACK`
2. `P1_CONSTITUTIONAL_PREFLIGHT`
3. `P2_TASK_ROUTING`
4. `P3_ARCHITECTURE_DECISION`
5. `P4_ALIGNMENT_AND_STUB_GATE`
6. `P5_RECURSIVE_IMPROVEMENT`
7. `P6_LEVERAGE_COMPRESSION`
8. `P7_FLAWLESS_VICTORY`

## Supersession Rule

The old pack remains source history. This clean pack is the active runtime kernel pack.

Do not re-import old profile, blueprint, audit, or contract files as active kernels unless a future migration explicitly promotes them through the duplicate kernel policy.

## What Was Removed From Active Runtime

- Profile/persona material.
- Duplicate blue sky audits.
- Build contracts that are source context rather than active kernels.
- `__MACOSX` files.
- Overlapping gap/stub kernels merged into `validate_eliminate_stubs.md`.
- Overlapping improvement/leverage instructions separated into bounded phases.

## Terminal Rule

`flawless_victory.contract.yaml` runs only after prior phase gates are complete. It is not a brainstorming prompt, not an audit prompt, and not a general kernel.

## Validator Layer

The pack now includes a validator layer under `runtime/kernel_pipeline/validators/`. Run:

```bash
python runtime/kernel_pipeline/run_validators.py
```

The validators enforce:

- canonical phase order from P0 through P7
- K01 -> K05 constitutional load order
- terminal-only `flawless_victory.contract.yaml` activation
- role-directory cardinality
- duplicate active-kernel detection
- phase-output contract alignment

This is the first self-policing layer for the superseding clean kernel pack.


## v3 Kernel Activation Planner

This pack now includes a deterministic activation planner:

```text
runtime/kernel_pipeline/planner/
├── TASK_ROUTING_RULES.yaml
├── ACTIVATION_PLAN_SCHEMA.yaml
├── plan_activation.py
├── KERNEL_ACTIVATION_PLAN.example.yaml
└── README.md
```

Use it to select the smallest valid kernel set for a task:

```bash
python runtime/kernel_pipeline/planner/plan_activation.py \
  "clean and dedupe this L9 kernel pack, then prepare a build contract" \
  --terminal \
  --out KERNEL_ACTIVATION_PLAN.yaml
```

Then run validators:

```bash
python runtime/kernel_pipeline/run_validators.py
```

The planner is not an executor. It emits the route, phases, active kernels, skipped kernels, required outputs, blockers, and Unknowns.


## v4 Universal Contract Compiler

The pack now compiles canonical runtime contracts before rendering to any tool-specific environment.

```text
Runtime Intent
→ Kernel Activation Plan
→ FINAL_EXECUTION_CONTRACT.yaml
→ VALIDATION_CONTRACT.yaml
→ HANDOFF_CONTRACT.yaml
→ adapter render
```

Added files:

```text
contracts/
├── execution_contract.schema.json
├── validation_contract.schema.json
├── handoff_contract.schema.json
└── adapter_render.schema.json

runtime/contract_compiler/
├── compile_execution_contract.py
├── compile_validation_contract.py
├── compile_handoff_contract.py
└── adapters/
    ├── claude_code.md
    ├── cursor.md
    ├── codex.md
    ├── chatgpt.md
    └── human_operator.md
```

Rule: Flawless Victory is terminal doctrine inside the universal execution contract, not a Claude-only output format.


## v5 Intent Graph Convergence

This pack now supersedes v4 by adding the missing compiler-grade intermediate representation path:

```text
Human Intent -> Intent Compiler -> Kernel Planner -> Universal Execution Contract -> Execution Graph -> Validation -> Adapter Render
```

New convergence files:

- `contracts/intent_contract.schema.json`
- `runtime/intent_compiler/`
- `runtime/execution_graph/`
- `EXECUTION_GRAPH.json`
- `EXECUTION_GRAPH.md`
- `COMMIT_PACK.md`
- `CONVERGENCE.md`

Run validators:

```bash
python runtime/kernel_pipeline/run_validators.py
```

## Roadmap: Deterministic Adapter Renderers

Adapter renderers are a planned next layer, but they must remain deterministic serialization modules, not new planning engines.

Before building renderer scripts, prove that `FINAL_EXECUTION_CONTRACT.yaml` and `EXECUTION_GRAPH.json` are stable across 2-3 real use cases. The renderer promotion rule is documented in `ROADMAP.md`.

Target future shape:

```text
runtime/contract_compiler/renderers/
├── render_claude_code.py
├── render_cursor.py
├── render_codex.py
├── render_chatgpt.py
└── render_human_operator.py
```

Rule: renderers serialize canonical plans only. They do not choose kernels, rewrite graph order, invent validation, or own execution logic.

