---
id: "l9-cognitive-runtime.context.agents__md"
title: "AGENTS"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "AGENTS.md"
content_hash: "ca87ab710547aa161acb60d725d1f8231206f1d5c14e8ce1fb92eab04f4c005b"
token_cost_estimate: 574
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "auditor"
description: "Unknown"
activation_signals: ["validate", "roadmap", "find", "agent", "contract"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
# AGENTS.md — operating instructions

Authority order is in [`CLAUDE.md`](CLAUDE.md). This file says how to work here, not
what outranks what.

## Source of truth

The ordering lives in [`CLAUDE.md`](CLAUDE.md) and is not repeated here — two files
ranking the same rungs is how they come to disagree. `ROADMAP.md` and `CONVERGENCE.md`
sit alongside `docs/SUPERSEDES.md` as context, below the contracts.

What this file adds is the terminal rung: **Unknown**. An agent that cannot find the
answer in that chain should say so rather than invent one. A fabricated contract field is worse than an unanswered question, because
the ladder will happily validate a shape nobody meant.

## Before you change anything

Read the contract that governs the file you are about to touch. The validation ladder
in `VALIDATION_CONTRACT.yaml` runs in order, and a change that satisfies
`adapter_render` while breaking `schema` fails at the earlier rung — so work outward
from the schema, not inward from the render.

## Always

- Run the full local gate before pushing (the block in `CLAUDE.md`). It mirrors
  `pr-check.yml` step for step.
- Keep `uv.lock` in the same commit as any dependency change. CI syncs `--frozen`.
- Keep runtime exports, schemas and `MANIFEST.json` synchronized when you add or move
  a kernel.
- Preserve `docs/SUPERSEDES.md`'s exclusions. Material is excluded from the active
  runtime deliberately; re-admitting it needs a stated reason in the PR.
- Treat mypy as strict, because it is. Do not add `# type: ignore` to move on — narrow
  the type or fix the call.

## Never

- Re-admit excluded source material into the active kernel tree without saying why.
- Relocate `runtime/` into `src/l9_cognitive_runtime`. The namespace is a baseline; the
  move is not planned work.
- Commit build artifacts. `dist/` is ignored apart from its tracked `README.md`, and
  the clean-checkout job fails on anything else.
- Weaken a test, a schema, or a ruff/mypy setting to get a green run. A failing gate is
  evidence; repair the cause it points at.
- Duplicate a kernel to work around `duplicate_active_kernel_scan`.

## Reporting

State what you ran and what it returned. If the suite was not run, say that plainly
rather than omitting it — an unstated gap reads as a pass to the next reader.
