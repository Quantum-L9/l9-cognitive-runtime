# Bounded Manus Cog MCP Adapter

The `l9-cognitive-runtime-manus-mcp` entrypoint provides a local stdio adapter for Manus while the independently authenticated Cog HTTP deployment remains under review. It is a narrow wrapper around the package-owned compiler surface, not a governance repository shell, generic runner, or deployment substitute.

The adapter starts only with `L9_MCP_TRANSPORT=stdio` and an explicit `L9_PACK_ROOT`. Startup uses `PackLoader` to verify every manifest-listed file before any MCP tool is registered. The pack root is connector configuration, never a tool input; callers cannot point Cog at an arbitrary repository or filesystem path.

| Tool | Purpose |
|---|---|
| `cog_runtime_capabilities` | Reports the fixed read-only surface and verified-pack provenance. |
| `cog_compile_intent` | Compiles the canonical intent contract. |
| `cog_plan_kernel_activation` | Returns the deterministic activation plan and execution ordering. |
| `cog_plan_context_requirements` | Returns the typed context-demand contract for a mission. |
| `cog_compile_runtime` | Compiles an in-memory runtime bundle against the bound pack. |
| `cog_validate_runtime_bundle` | Compiles and validates bundle integrity. |

No tool executes an execution graph, invokes a shell, writes a repository, accepts a pack path, or exposes arbitrary Cog code. The same six compiler operations remain the contract for a later OAuth-protected remote MCP deployment. This stdio adapter exposes them under `cog_` names (`cog_runtime_capabilities`, and the five siblings in the table). The current HTTP MCP surface still registers the unprefixed `READ_ONLY_TOOLS` names (for example `runtime_capabilities`). Replacing this connector with that HTTP deployment is not a drop-in tool-name swap until those names are aligned.

## Connector posture

Install a built wheel into a dedicated, connector-owned virtual environment. Build the sealed pack from the same full source revision, then configure Manus to run the console entrypoint with only these environment values:

```text
L9_MCP_TRANSPORT=stdio
L9_PACK_ROOT=/absolute/path/to/verified/pack
```

Before enabling the connector, verify MCP initialization, the exact six-tool inventory, one compile call, and a tampered-pack startup failure. Do not place OAuth credentials, GitHub credentials, Infisical credentials, deployment broker tokens, or arbitrary paths in the connector configuration.
