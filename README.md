# L9 Cognitive Runtime Kernel Pack - Clean Superseding Pack

This pack supersedes the uploaded `L9 Cognitive Runtime (kernels).zip` by deduping overlapping kernel material into a smaller kernel-first runtime layout.

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

## MCP client configuration (Claude Code / Cursor)

Project-scoped configs (OAuth discovery; no static credentials):

- Claude Code: `.mcp.json`
- Cursor: `.cursor/mcp.json`

Setup, sanitized OAuth transcript, and secret-scanner usage: [`docs/ops/mcp-client-setup.md`](docs/ops/mcp-client-setup.md).

```bash
python scripts/scan_mcp_secrets.py .mcp.json .cursor/mcp.json
```

Production conformance + release gates: [`docs/ops/mcp-release-gates.md`](docs/ops/mcp-release-gates.md).

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



## MCP stdio (read-only)

Local stdio MCP server for Claude Code / Cursor (no HTTP, no writes):

```bash
export L9_PACK_ROOT="$(pwd)"
uv run --no-build l9-cognitive-runtime-mcp
```

Tools: `runtime_capabilities`, `compile_runtime`, `get_bundle_digests`, `list_pack_manifest`, `validate_pack_path`.
