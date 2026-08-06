# GMP Report 001 — Establish installable Python package and build baseline

**Run ID:** GMP-L9CR-MCP-001
**Date:** 2026-08-06
**Target Branch:** feat/mcp-001
**Scope:** pyproject.toml, src/l9_cognitive_runtime/, tests/, .gitignore, README.md (additive package baseline)
**Commit Message:** `build: establish installable cognitive runtime package`
**Contract:** L9CR-MCP-001
**Campaign:** L9CR-MCP (manual controller; no program.yaml; patterned on CG-PES-RUN2-HARDENING)

## 1. PLAN

### Context

Convert the repository into an installable Python project without changing cognitive-runtime semantics. Preserve existing runtime, contracts, kernels, manifests, and roadmap.

### Campaign operating model (no program.yaml)

- Serial contracts PR-001 → PR-014 (015/016 optional)
- Per contract: GMP 0–6 → commit → push → open PR → subscribe → dispatch `l9-pr-remediation` Task (≤3 cycles, never merge)
- Dependent contracts stack on prior branch until prior merges to `main`

### Locked TODO table

| ID | File | Operation | Anchor | Status |
|---|---|---|---|---|
| T-001 | pyproject.toml | Create | new file | APPLIED |
| T-002 | src/l9_cognitive_runtime/__init__.py | Create | new file | APPLIED |
| T-003 | tests/test_package_import.py | Create | new file | APPLIED |
| T-004 | .gitignore | Replace | full file | APPLIED |
| T-005 | README.md | Insert | after title block | APPLIED |
| T-006 | reports/GMP-Report-001-mcp-001-package-baseline.md | Create | new file | APPLIED |

### MODIFICATION LOCK

**May-modify:** `pyproject.toml`, `src/l9_cognitive_runtime/__init__.py`, `tests/test_package_import.py`, `.gitignore`, `README.md`, `reports/GMP-Report-001-mcp-001-package-baseline.md`

**Must-not-modify:** `runtime/**`, `contracts/**`, kernel YAML/MD, `MANIFEST.json`, `FINAL_EXECUTION_CONTRACT.yaml`, `EXECUTION_GRAPH.*`, compiler/MCP/auth/deploy surfaces, `.github/**` (absent), PyPI publish config

### ADRs CONSULTED

- Contract `pr_001__l9cr-mcp-001.md`
- Campaign pattern CG-PES-RUN2-HARDENING (serial work items, draft PR, Cursor Task remediation, human-only merge)
- GMP `docs/gmp_protocol` phase contracts via skill references

### MEMORY_PREFETCH

Graphiti conflicts observed (unrelated INTEGRATES_WITH / REQUIRES facts). Graphite namespace `igor-workspace` unauthorized for principal `local-operator`.

### CODE_GRAPH_BASELINE

SKIPPED — package scaffold / docs / tests only.

## 2. CHANGES

| File | Action | Notes |
|---|---|---|
| pyproject.toml | Create | hatchling build, pytest/ruff/mypy/build tool config |
| src/l9_cognitive_runtime/__init__.py | Create | `__version__ = "0.1.0"` baseline export |
| tests/test_package_import.py | Create | import + version smoke test |
| .gitignore | Replace | ignore build/cache/venv artifacts |
| README.md | Insert | Development Setup section |
| reports/GMP-Report-001-mcp-001-package-baseline.md | Create | this evidence report |

## 3. TODO → CHANGE MAP

| TODO | Phase | Result |
|---|---|---|
| T-001 | 2 | APPLIED — pyproject.toml |
| T-002 | 2 | APPLIED — package init |
| T-003 | 2 | APPLIED — import test |
| T-004 | 2 | APPLIED — gitignore |
| T-005 | 2 | APPLIED — README setup |
| T-006 | 6 | APPLIED — evidence report |

## 4. VALIDATION

| Gate | Result |
|---|---|
| Isolated `pip install -e ".[dev]"` (uv) | PASS |
| `import l9_cognitive_runtime` | PASS (`0.1.0`) |
| pytest | PASS (1 passed) |
| ruff check src tests | PASS |
| mypy | PASS (2 source files) |
| `python -m build` (wheel + sdist) | PASS |
| Wheel contents include `l9_cognitive_runtime/__init__.py` | PASS |
| `python runtime/kernel_pipeline/run_validators.py` | PASS (existing behavior unchanged) |
| Build artifacts not staged | PASS (dist/*.whl ignored) |

Recommendation: PROCEED

## 5. INVARIANTS CHECK

- Protected / out-of-scope paths untouched (`runtime/`, compilers, MCP, auth, deploy)
- No runtime move
- No stubs / placeholders in package surface
- Deferred migration: relocate runtime modules under `src/` deferred to later contracts (002+)

## 6. DECLARATION

Phases 0-6 complete. No assumptions. No drift.
GMP run GMP-L9CR-MCP-001 finalized.
No further changes permitted.

## 7. GRAPHITI MEMORY EVIDENCE

- Prefetch conflicts listed (unrelated to this package baseline)
- No episode write in this run (campaign orchestration continues on subsequent contracts)
