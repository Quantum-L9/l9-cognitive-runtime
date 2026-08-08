# Evidence Report — MCP-008B read-only stdio MCP server

- **contract_id:** L9CR-MCP-PR-REMEDIATION-001 / logical contract MCP-008B
- **replacement_branch:** `rem/mcp-008b`
- **base:** `rem/mcp-008a`
- **supersedes source PR:** #9 stdio half (commit `5ce7192c`, safety tag `backup/pr-9-5ce7192c`)
- **primary concern:** expose the deterministic compiler over MCP stdio, read-only

## Corrections vs. the source implementation

The source exposed the **wrong tool/resource surface** and defaulted the pack to
the working directory. This PR implements the contract surface against the real
`mcp` 2.0 SDK (`MCPServer`):

| Area | Source | This PR (contract) |
|---|---|---|
| Tools | `get_bundle_digests`, `list_pack_manifest`, `validate_pack_path` … | `runtime_capabilities`, `compile_intent`, `plan_kernel_activation`, `compile_runtime`, `validate_runtime_bundle` |
| Resources | `runtime://capabilities`, `pack://manifest` | `l9://runtime/version`, `l9://runtime/capabilities`, `l9://packs/{pack_ref}/manifest`, `l9://packs/{pack_ref}/schemas/{schema_name}`, `l9://packs/{pack_ref}/kernels/{kernel_id}` |
| Pack root | defaulted to `Path.cwd()` | **required** `L9_PACK_ROOT`; no fallback |

## Invariants (phase_5 stdio_pr) — all enforced + tested

| Invariant | Evidence |
|---|---|
| stdio only; non-stdio refused | `test_main_rejects_non_stdio_transport` |
| explicit pack_ref required; no cwd fallback | `test_main_requires_pack_root` |
| no tool executes shell / mutates repo | `test_no_mutating_or_shell_tool_registered`, capabilities `writes=false`, `execution=false`, `shell=false` |
| no arbitrary filesystem path | pack path resolution is confined via `pack.resolve` (traversal-safe); `test_missing_kernel_resource_rejected` |
| every compile requires a verified pack; provenance on success | `test_compile_runtime_tool_success` asserts `provenance.manifest_digest` |

## Required end-to-end tests (phase_5)

`test_wire_initialize_list_and_call` runs a full in-memory protocol round-trip:
`initialize` → `tools/list` (exactly the five tools) → `tools/call` → clean
shutdown. Plus: tool success, invalid input (raises), resource read success,
unknown pack_ref / missing resource failure. **12/12 pass.**

## Client smoke / certification

Local stdio client configuration for Claude Code and Cursor is documented in
`docs/ops/mcp-stdio-client-setup.md` (no credentials in stdio config). **Live
human client certification is REQUIRED and not yet performed** — it must be
signed by a reviewer who is not the implementation agent, and is not claimed
here (see contract stop_conditions / definition_of_done).

## Dependency

Adds `mcp>=2.0.0` (pulls starlette/uvicorn/anyio/pyjwt via the SDK); `uv.lock`
updated and validated under `uv sync --frozen`.

## Commands executed (this branch head)

```
uv sync --extra dev --frozen   # locked (CI parity)
uv run ruff check .            # All checks passed!
uv run ruff format --check .   # 33 files already formatted
uv run mypy src                # Success: no issues found in 14 source files
uv run python -m pytest -q     # 65 passed
uv run python -m build         # Successfully built sdist + wheel
```
