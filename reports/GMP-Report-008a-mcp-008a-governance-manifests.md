# Evidence Report — MCP-008A governance consumer manifests

- **contract_id:** L9CR-MCP-PR-REMEDIATION-001 / logical contract MCP-008A
- **replacement_branch:** `rem/mcp-008a`
- **base:** `rem/mcp-007`
- **source:** the governance half of source PR #9 (commit `a6aabac5`), split away from the stdio MCP half (`5ce7192c` → MCP-008B)
- **primary concern:** restore the Cursor-Governance `make pr` consumer manifests — **only**

## Split rationale (F-PR9-MIXED)

Source PR #9 mixed governance-manifest restoration with the stdio MCP feature.
This PR carries **only** the governance manifests; the stdio MCP server is a
separate PR (MCP-008B). No MCP source, no runtime feature changes.

## Files (7, config only)

```
commands/COMMANDS_MANIFEST.yaml
rules/RULES-MANIFEST.json
rules/RULES-MANIFEST.md
rules/RULES-MANIFEST.yaml
skills/AUTONOMY_MANIFEST.yaml
environment/claude-code/generated/skill-registry.json
environment/claude-code/settings.template.json
```

These are empty/minimal consumer manifests required by `make pr sync --check`:
no repo-local skills, empty rule/skill registries, no secrets. They are `.yaml`
/ `.json` / `.md` — outside the ruff/mypy/pytest surface — so the quality gates
are unaffected.

## Commands executed (this branch head)

```
uv run ruff check .            # All checks passed!
uv run mypy src                # Success: no issues found in 13 source files
uv run python -m pytest -q     # 53 passed
```

## Residual / deviations

- The source PR #5 also leaked a `Makefile` and pre-commit config; those were
  dropped at MCP-004 and are **not** reintroduced here — `a6aabac5` (the
  canonical "restore make pr consumer manifests" commit) does not include them.
