# l9-cognitive-runtime — private Agent Plugin

Packages the existing L9 Cognitive Runtime as one private Agent Plugin
([Agent Plugins 1.0.0](https://agent-plugins.org/specification)).

| Part | Owner | What it is |
|---|---|---|
| `plugin.json` | this package | Portable manifest. Identity matches `pyproject.toml` (`l9-cognitive-runtime`, `0.1.0`). |
| `skills/compile-runtime-bundle/SKILL.md` | this package | The one workflow skill: capabilities → context plan → external governed context → plan-bound compile → digest/provenance checks. |
| MCP tools | existing server (`src/l9_cognitive_runtime/mcp`) | The six read-only tools. This package adds none and changes none. |
| Compilation | existing runtime | Sole compiler. The plugin carries no execution or contract logic. |

## Why there is no `mcp.json`

The portable `mcp.json` would have to name either a stdio command with its
required environment or a remote URL. Neither can be stated truthfully here:

- **stdio** — the server refuses to start without `L9_PACK_ROOT` (no
  working-directory fallback). A pack root is a machine-specific path to a
  verified pack; `${PLUGIN_ROOT}` does not contain one and installed plugins are
  copied to a host cache, so any value would be an invented path.
- **streamable-http** — the hosted endpoint and its OAuth registration are
  operator-owned and not yet bound to this package.

So the connection is configured by the operator in the host, and the skill
fails closed when it is absent. Adding `mcp.json` later is a manifest-only
change once a real endpoint exists.

## Connection prerequisites

One of:

1. **Local stdio** (desktop hosts that allow local MCP servers)
   - Python ≥ 3.11 and the package installed from this repository, which provides
     the `l9-cognitive-runtime-mcp` console script.
   - A verified runtime pack. Build one from a checkout:

     ```bash
     uv sync --extra dev --frozen
     uv run python -m l9_cognitive_runtime.deployment \
       --source-root . --destination <pack-dir> --source-revision "$(git rev-parse HEAD)"
     ```

   - Register the server in the host as `l9-cognitive-runtime`, command
     `l9-cognitive-runtime-mcp`, environment `L9_PACK_ROOT=<pack-dir>` (absolute
     path). `L9_MCP_TRANSPORT` may be omitted; any value other than `stdio` is
     refused.
2. **Hosted** — the operator-registered HTTPS deployment of the same server
   (`l9-cognitive-runtime-http`, path `/v1/mcp`, OAuth 2.0 bearer). Connection and
   account authorization are done in the host UI; this package stores no URL,
   client id, or credential.

## Blocked behavior (by design)

| Condition | Observed result |
|---|---|
| `L9_PACK_ROOT` unset | server prints `error: L9_PACK_ROOT is required (no working-directory fallback)`, exits `2` |
| `L9_PACK_ROOT` not a directory / pack fails verification | server refuses to start (`InvalidValueError`) |
| `L9_MCP_TRANSPORT` not `stdio` | exits `2` |
| server not connected | skill stops: "The L9 Cognitive Runtime MCP server is not connected." |
| stale `expected_context_plan_id` | tool error `context planning inputs changed; replan required` |
| malformed `context_snapshot` | tool error `context_snapshot is not a valid governed snapshot: …` |
| hosted call without a validated token | `401` / `authenticated principal required` |

## Human UI installation (operator)

Follows <https://developers.openai.com/plugins/build/plugins> (local/private
marketplace). Not performed or verified by this package:

1. Add a repo marketplace entry in `.agents/plugins/marketplace.json` with
   `"source": {"source": "local", "path": "./plugins/l9-cognitive-runtime"}`,
   or copy this directory to a personal marketplace.
2. Restart the desktop app and confirm `l9-cognitive-runtime` is listed.
3. Connect the MCP server (local stdio or hosted, above).
4. Run the first compilation smoke from a new conversation.

## First compilation smoke

In the host, after connecting:

> Use compile-runtime-bundle to compile the mission "Update greeting text." with
> no governed context.

Expected: `runtime_capabilities` reports `read_only` with `writes`, `execution`
and `shell` false; `plan_context_requirements` returns a
`context-plan.sha256:…` id; `compile_runtime` with that `expected_context_plan_id`
returns the same id, a `run_id`, `resource_uri` `l9://runs/<run_id>`, and
`execution_packet.compiled_task_context_digest == digests.context`.

The same sequence is reproducible without a host — `tests/test_plugin_package.py`
drives the skill's workflow against the real server, and from a clean checkout:

```bash
uv sync --extra dev --frozen --no-install-project --no-build
PYTHONPATH=src uv run --no-sync --no-build python -m pytest -q tests/test_plugin_package.py
```
