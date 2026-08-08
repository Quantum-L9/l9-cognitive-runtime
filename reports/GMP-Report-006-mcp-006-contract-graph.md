# Evidence Report — MCP-006 contract-derived execution graphs

- **contract_id:** L9CR-MCP-PR-REMEDIATION-001 / logical contract MCP-006
- **replacement_branch:** `rem/mcp-006`
- **base:** `rem/mcp-005`
- **supersedes source PR:** #7 (`feat/mcp-006`, safety tag `backup/pr-7-3bb1073c`)
- **primary concern:** derive the execution graph from the contract; reject cycles/unresolved deps; determinism

## What changed

The graph is no longer a hardcoded in-memory `DEFAULT_PHASES` table. `service`
now calls `derive_execution_graph(execution)`: nodes derive from the contract's
`execution_sequence`, edges derive from that declared order, and the result is
validated acyclic with a topological order that must match the declared
sequence.

## Phase-1 remediations applied (findings.yaml / acceptance-matrix.yaml)

| Remediation | Fix |
|---|---|
| **remove validation_gates default** | Source derived `gates = list(...) or ["pipeline_order",...]`. The silent default is removed: `validation_gates` now derive **only** from `contract.validation_requirements` (`test_validation_gates_derive_from_contract_no_default`). |
| **golden fixtures** | Added `tests/fixtures/graph/execution_graph_golden.json`; `test_derived_graph_matches_golden` locks the canonical graph byte-for-byte. |
| **clarify scheduler AC** | Clarified in the module docstring: derivation is a pure deterministic transform, **not** a runtime scheduler (the GDS APScheduler is a separate, dormant subsystem outside this compiler). |

## Contract acceptance (phase_3 contract_graphs)

| Requirement | Evidence |
|---|---|
| Nodes derive from contract elements | `test_nodes_and_edges_derive_from_sequence`, `test_graph_is_contract_derived` |
| Edges derive from declared dependencies | `test_nodes_and_edges_derive_from_sequence` (edge pairs follow sequence) |
| Cycles rejected | `test_cycle_rejected` (topological sort) |
| Unresolved dependencies rejected | `test_missing_dependency_rejected` |
| Identical contracts → identical canonical graphs | `test_identical_contracts_deterministic` + golden regression |

## Commands executed (this branch head)

```
uv run ruff check .            # All checks passed!
uv run ruff format --check .   # 29 files already formatted
uv run mypy src                # Success: no issues found in 13 source files
uv run python -m pytest -q     # 46 passed
uv run python -m build         # Successfully built sdist + wheel
```

## Residual / deviations

- The `valid_pack` fixture's `execution_sequence` now uses recognized phase
  steps so the derived graph maps to the canonical phases (terminal `emission`).
- CI gate enforcement (`pr-check.yml`) lands at MCP-007; evidence above is local.
