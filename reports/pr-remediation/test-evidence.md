# Test evidence — L9CR-MCP-PR-REMEDIATION-001

## Phase 0–1
No quality-gate command suite executed yet against remediation branches (inventory/audit only).

## Planned command matrix (per clean PR)
```
python -m pytest
ruff check .
ruff format --check .
mypy src
python -m build
```

## Observed CI (source PRs, 2026-08-06)
| PR | Sonar | Semgrep |
|----|-------|---------|
| 2,3,5,6,7,9,10,11,12,16,17 | SUCCESS | SUCCESS |
| 4,8,13,14,15 | FAILURE | SUCCESS |

Sonar SUCCESS alone is insufficient evidence per contract.


## rem/mcp-002..005 (2026-08-06)

| Branch | pytest | ruff | mypy |
|--------|--------|------|------|
| rem/mcp-002 | 11 passed | pass | pass |
| rem/mcp-003 | 16 passed | pass | pass |
| rem/mcp-004 | 23 passed | pass | pass |
| rem/mcp-005 | 31 passed | pass | pass |

Commands: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run mypy src`
