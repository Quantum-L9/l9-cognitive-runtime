# Evidence Report — MCP-007 hardening suites + CI gate enforcement

- **contract_id:** L9CR-MCP-PR-REMEDIATION-001 / logical contract MCP-007
- **replacement_branch:** `rem/mcp-007`
- **base:** `rem/mcp-006`
- **supersedes source PR:** #8 (`test/mcp-007`, safety tag `backup/pr-8-ac57425a`)
- **primary concern:** release-grade hardening tests **and** the CI job that enforces the gates

## What changed

Adds `.github/workflows/pr-check.yml` — the first workflow that actually
executes the quality gates in CI — and a hardening suite covering golden
determinism, concurrency isolation, path traversal, and strict-parse blocking.
This closes the "gates are local-only / unenforced" gap flagged on rungs 1–6.

## Phase-1 remediations applied (findings.yaml / commit-map.yaml)

| Finding / action | Fix |
|---|---|
| **F-PR8-GHA** — unpinned actions; unlocked uv | Actions pinned to immutable commit SHAs (`actions/checkout@d23441a…` = v6.1.0, `astral-sh/setup-uv@11f9893…` = v8.3.2); `uv sync --extra dev --frozen` (locked). |
| **drop `ac57425a`** (governance-restore leak) | Not reapplied — governance manifests are deferred to MCP-008A. This PR is hardening + CI only. |
| **add mypy** | CI runs `mypy src` (strict), plus `ruff check`, `ruff format --check`, `pytest`, and `python -m build`. |
| **commit goldens** | The committed graph golden (MCP-006) is now enforced by the CI `pytest` step. |
| **build from a clean checkout** | Dedicated `clean-build` job builds sdist+wheel and asserts the working tree stays clean (no committed dist artifacts). |
| **offline tests / concurrency** | All tests are offline; `test_concurrency_compile_isolation` runs 8 compiles across 4 threads and asserts per-mission isolation. |

## CI matrix (phase_4 minimum_test_matrix)

- Python **3.11** and **3.12** on **linux** (`ubuntu-latest`).
- Commands: `pytest`, `ruff check`, `ruff format --check`, `mypy src`, `python -m build`.

## Command evidence (local, this branch head)

```
uv sync --extra dev --frozen   # Audited 21 packages (locked, CI parity)
uv run ruff check .            # All checks passed!
uv run ruff format --check .   # 30 files already formatted
uv run mypy src                # Success: no issues found in 13 source files
uv run python -m pytest -q     # 53 passed
uv run python -m build         # Successfully built sdist + wheel
```

## Residual / deviations

- The hardening suite compiles against the `valid_pack` fixture (the fail-closed
  service requires a manifest-verified pack; the mutable repo root does not verify).
- SonarCloud/Semgrep remain GitHub-App integrations (not workflow files); this PR
  adds the missing gate-executing workflow rather than replacing those.
- Branch-protection required-context registration is a repository setting outside
  the tree; it must be pointed at `pr-check` after merge (human/admin step).
