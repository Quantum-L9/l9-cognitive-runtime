# Local stdio MCP client setup (L9CR-MCP-008B)

The `l9-cognitive-runtime-mcp` console script starts a **read-only, stdio-only**
MCP server. It requires an explicit `L9_PACK_ROOT` (a manifest-verified pack);
there is no working-directory fallback and no credentials are involved.

> This document covers **local stdio** only. Hosted (Streamable HTTP + OAuth)
> client configuration is a later contract (MCP-013) and is intentionally out of
> scope here. Do not add Authorization headers, bearer tokens, or access tokens
> to a stdio config — the transport is local and unauthenticated by design.

## Tools (read-only)

`runtime_capabilities`, `compile_intent`, `plan_kernel_activation`,
`compile_runtime`, `validate_runtime_bundle`.

## Resources

`l9://runtime/version`, `l9://runtime/capabilities`,
`l9://packs/{pack_ref}/manifest`, `l9://packs/{pack_ref}/schemas/{schema_name}`,
`l9://packs/{pack_ref}/kernels/{kernel_id}`.

## Claude Code

```bash
claude mcp add --scope local l9-cognitive-runtime \
  --env L9_PACK_ROOT=/absolute/path/to/verified/pack \
  -- uv run l9-cognitive-runtime-mcp
```

Equivalent `.mcp.json` (local scope):

```json
{
  "mcpServers": {
    "l9-cognitive-runtime": {
      "command": "uv",
      "args": ["run", "l9-cognitive-runtime-mcp"],
      "env": { "L9_PACK_ROOT": "/absolute/path/to/verified/pack" }
    }
  }
}
```

## Cursor

`.cursor/mcp.json` (local stdio):

```json
{
  "mcpServers": {
    "l9-cognitive-runtime": {
      "command": "uv",
      "args": ["run", "l9-cognitive-runtime-mcp"],
      "env": { "L9_PACK_ROOT": "/absolute/path/to/verified/pack" }
    }
  }
}
```

## Automated smoke evidence

`tests/test_mcp_stdio.py::test_wire_initialize_list_and_call` performs a full
in-memory protocol round-trip against this server: `initialize` →
`tools/list` (exactly the five read-only tools) → `tools/call runtime_capabilities`
→ clean session shutdown. Tool/resource success and failure paths are covered by
the rest of that module.

## Human client certification — REQUIRED, not yet performed

Per the remediation contract, live Claude Code and Cursor certification must be
signed by a human reviewer who is **not** the implementation agent. That
certification is **pending** and is not claimed here. Sanitized transcripts of a
live `claude mcp add` / Cursor connection should be attached at certification
time; no credentials appear in stdio configuration.
