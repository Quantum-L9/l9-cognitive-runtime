# CLAUDE.md — authority pointer

This file exists to be **loaded**, not to be comprehensive. It is deliberately short
so it always fits, and it duplicates no doctrine: it says where authority lives and
what outranks what.

Until now this repository carried none of the four root agent-docs — no `CLAUDE.md`,
`AGENTS.md`, `INVARIANTS.md` or `ARCHITECTURE.md`. Its law was real and unloadable at
the same time, which is why an inbound PR pack had to ship `INVARIANTS.md` for verbatim
copy as a step of its own execution order. This file closes the loadable half.

## Authority chain

Highest first. A lower rung never overrides a higher one.

1. **Executable validators and CI** — `.github/workflows/pr-check.yml` is the final
   word on whether a change is acceptable. A passing gate outranks any prose here.
2. **Contracts** — `FINAL_EXECUTION_CONTRACT.yaml`, `VALIDATION_CONTRACT.yaml`,
   `HANDOFF_CONTRACT.yaml`, and the JSON Schemas under `contracts/`. These define the
   validation ladder (`format → schema → pipeline_order → kernel_roles →
   duplicate_active_kernel_scan → activation_planner → contract_compiler →
   adapter_render → evidence_manifest`).
3. **`MANIFEST.json`** — pack identity, version, supersession and the file inventory.
4. **`rules/RULES-MANIFEST.{json,yaml,md}`** — the rule registry.
5. **`AGENTS.md`** — operating instructions for agents in this repository.
6. **`docs/SUPERSEDES.md`** — what this pack supersedes and what is deliberately
   excluded from the active runtime.
7. **Agent-invented contracts** — none. A rule you find yourself designing belongs in
   one of the rungs above, in a PR.

This file is not a rung. It only names them.

## The things most often got wrong here

- **The kernel tree is curated, not accumulated.** `docs/SUPERSEDES.md` records that
  old blueprints, audits and README variants are *excluded from the active runtime* —
  excluded, not deleted. Re-admitting one because it looks useful is the failure this
  pack was built to end. `duplicate_active_kernel_scan` is a ladder rung for a reason.
- **`src/l9_cognitive_runtime` is a baseline namespace only.** `runtime/` semantics are
  unchanged and are **not** relocated by it. Do not "finish the migration" — there
  isn't one.
- **The lockfile is frozen in CI.** Every job runs `uv sync --extra dev --frozen`. A
  change that needs a new dependency must update `uv.lock` in the same commit, or CI
  fails on the sync step before it reaches a test.
- **`dist/` is ignored except for one tracked `dist/README.md`.** That is deliberate,
  not drift. CI asserts the working tree stays clean after a build, so a committed
  build artifact fails the `build from clean checkout` job.

## Verify before pushing

```bash
uv sync --extra dev --frozen
uv run --no-sync --no-build ruff check src tests
uv run --no-sync --no-build ruff format --check src tests
uv run --no-sync --no-build mypy src tests          # strict
uv run --no-sync --no-build python -m pytest -q
git status --porcelain                              # must be empty
```

That mirrors `pr-check.yml` exactly. Running it locally is the only way to know a push
will be green before it is pushed.

## CI topology

| Workflow | Trigger | What it proves |
|---|---|---|
| `pr-check.yml` | pull requests | ruff lint, ruff format, mypy strict, pytest — then a separate build from a clean checkout asserting no committed `dist/` artifacts |
| `container-smoke.yml` | see workflow | the image builds and starts |
| `release-staging.yml` | see workflow | staging release path |

Required branch-protection contexts are repository settings outside this tree. Verify
them; do not infer them from the presence of a workflow file.
