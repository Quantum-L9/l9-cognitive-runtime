# MCP client certification (Claude Code + Cursor)

Manual certification before any production release (L9CR-MCP-014).

Record results in `release/mcp-release-metadata.json` (`client_certifications`).

## Shared prerequisites

- Hosted MCP URL reachable; image digest pinned.
- Project configs from `.mcp.json` / `.cursor/mcp.json` (no static credentials).
- Operator can complete OAuth in a browser.

## Claude Code certification

| Step | Action | Pass criteria |
|------|--------|---------------|
| C1 | Load project `.mcp.json` | Server `l9-cognitive-runtime` listed |
| C2 | Complete OAuth on first call | Token stored outside repo; config unchanged |
| C3 | Call `runtime_capabilities` | Returns version + read-only tool list |
| C4 | Call `compile_runtime` with a test mission | Digests present; no repo mutation |
| C5 | Attempt a non-registered mutating tool name | Client/server reject |

## Cursor certification

| Step | Action | Pass criteria |
|------|--------|---------------|
| K1 | Load `.cursor/mcp.json` | Server `l9-cognitive-runtime` listed |
| K2 | Complete OAuth on first call | Token stored in Cursor secret store |
| K3 | Call `runtime_capabilities` | Same tool set as Claude certification |
| K4 | Call `get_run` for another principal's id | Denied / empty (isolation) |
| K5 | Confirm no `Authorization` header in committed JSON | `scan_mcp_secrets.py` PASS |

## Sign-off

Both certifications must be `pass` with operator, timestamp (UTC), and git SHA recorded in release metadata before the release gate can pass.
