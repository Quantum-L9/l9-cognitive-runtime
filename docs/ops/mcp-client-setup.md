# Claude Code and Cursor MCP client setup (L9CR-MCP-013)

Project-scoped configs (no static credentials):

| Client | Config path |
|--------|-------------|
| Claude Code | [`.mcp.json`](../../.mcp.json) |
| Cursor | [`.cursor/mcp.json`](../../.cursor/mcp.json) |

Both point at the hosted Streamable HTTP endpoint `https://runtime.example/v1/mcp`. Replace the host with your deployment URL; keep OAuth discovery client-side.

## OAuth (required)

1. Client receives `401` with protected-resource / WWW-Authenticate discovery.
2. Operator completes browser OAuth against the authorization server.
3. Client stores tokens in its own secret store — **never** in `.mcp.json` / `.cursor/mcp.json`.

Sanitized transcript shape (tokens redacted):

```text
→ GET /v1/mcp
← 401 WWW-Authenticate: Bearer realm="mcp", resource_metadata="..."
→ (browser OAuth; code exchange out of band)
→ tools/call runtime_capabilities
← ok { "tools": [...], "version": "..." }
```

## Local stdio (optional, no OAuth)

For pack-local development without a hosted URL, run stdio via:

```bash
uv run --no-build l9-cognitive-runtime-mcp
```

Do not add PATs, `Authorization` headers, or API keys to the committed JSON files.

## Secret scanner

```bash
python scripts/scan_mcp_secrets.py .mcp.json .cursor/mcp.json
```

CI runs the same check. Injecting a bearer header into a fixture must FAIL; the committed configs must PASS.
