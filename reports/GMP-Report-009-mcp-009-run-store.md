# Evidence Report — MCP-009 isolated MCP run result store

- **contract_id:** L9CR-MCP-PR-REMEDIATION-001 / logical contract MCP-009
- **replacement_branch:** `rem/mcp-009`
- **base:** `rem/mcp-008b`
- **supersedes source PR:** #10 (`feat/mcp-009`, safety tag `backup/pr-10-9b57b10c`)
- **primary concern:** bounded, isolated, ownership-aware run artifacts

## What changed

`InMemoryRunStore` (collision-resistant 128-bit `token_urlsafe` IDs, RLock,
TTL + max-entry LRU bound, per-principal ownership) is wired into the MCP
server: `compile_runtime` stores an isolated run and returns `run_id` +
`resource_uri`; a new `l9://runs/{run_id}` resource retrieves it. The stdio
tool surface stays the five approved tools (retrieval is a resource).

## Phase-1 remediations applied (findings.yaml)

| Finding / action | Fix |
|---|---|
| **typed not-found** (source `get_run` returned `{"found": false}`) | `RunStore.require` raises typed `RunNotFoundError`; the `l9://runs/{run_id}` resource surfaces it. |
| **anti-enumeration** | unknown, expired, and cross-principal lookups raise the **same** `RunNotFoundError` (`test_require_anti_enumeration_cross_principal`). |
| **concurrent test** | `test_concurrent_creates_do_not_overwrite` — 200 creates / 8 threads, all IDs unique and retrievable. |
| **no raw bodies retained** | only the derived result is stored (`test_compile_stores_isolated_run` asserts no `mission`/`intent`); payload is copied, not aliased (`test_payload_is_copied_not_aliased`). |
| **principal bind later** (F-PR10-PRINCIPAL) | stdio uses a single `LOCAL_PRINCIPAL`; the store API already takes a principal, so hosted OAuth binds it to the token subject in MCP-011C — documented as a pre-auth limitation. |

## Contract acceptance (phase_6)

| Requirement | Test |
|---|---|
| Run IDs collision-resistant | `test_collision_resistant_ids` |
| Bounded by TTL and max entries | `test_ttl_eviction`, `test_lru_capacity_bound` |
| Concurrent calls cannot overwrite | `test_concurrent_creates_do_not_overwrite` |
| Unknown/expired → typed not-found | `test_require_raises_typed_not_found_for_unknown`, `test_require_raises_for_expired` |
| No run artifact crosses run IDs | `test_cross_principal_isolation` + isolation tests |
| API compatible with later principal ownership | `principal` parameter throughout |
| End-to-end retrieval + unknown failure | `test_run_resource_retrieval`, `test_unknown_run_resource_rejected` |

## Commands executed (this branch head)

```
uv run ruff check .            # All checks passed!
uv run ruff format --check .   # 36 files already formatted
uv run mypy src                # Success: no issues found in 15 source files
uv run python -m pytest -q     # 77 passed
uv run python -m build         # Successfully built sdist + wheel
```
