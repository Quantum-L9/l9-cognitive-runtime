# FINAL FINDINGS — MCP Python SDK 2.0.0 → 2.1.1

Phase 1 of `l9cr_straight_line_chatgpt_mcp_deploy` v1.0.0.

## Revisions

| Field | Value |
|---|---|
| Contract observed baseline | `28f5b4b2450299de34f2d2d69bea32ece09363b1` |
| `origin/main` at phase start | `28f5b4b2450299de34f2d2d69bea32ece09363b1` (identical — no intervening changes) |
| Base SHA for this change | `28f5b4b2450299de34f2d2d69bea32ece09363b1` |
| Head SHA | recorded at commit time on `claude/l9-chatgpt-mcp-deploy-vpevgd` |

## Dependency diff

| Package | Before | After |
|---|---|---|
| `mcp` (locked) | 2.0.0 | **2.1.1** |
| `mcp-types` (locked, transitive) | 2.0.0 | **2.1.1** |
| `pyproject.toml` constraint | `mcp>=2.0.0` | `mcp>=2.1.1` |

`uv lock --upgrade-package mcp --upgrade-package mcp-types` moved **only** those two
entries. No other transitive dependency changed: `httpx2`, `starlette`, `pydantic`,
`sse-starlette`, `uvicorn`, `pyjwt`, `opentelemetry-api` and the rest resolve to the
same pinned versions as on the baseline. `mcp` 2.1.1's `Requires-Dist` differs from
2.0.0's in exactly one line (`mcp-types==2.0.0` → `mcp-types==2.1.1`).

## MCP API compatibility findings

Ground truth was the installed wheels, diffed module-by-module, cross-checked against
the upstream v2 migration guide (`py.sdk.modelcontextprotocol.io/v2/migration/`).

**Module inventory is purely additive.** 2.1.1 adds exactly one module,
`mcp/server/fastmcp.py`, which is a migration shim that raises `ModuleNotFoundError`
pointing at the v1→v2 rename. Nothing was removed.

**Every signature this repository calls is unchanged**: `MCPServer(name=, version=,
instructions=)`, `@mcp.tool()`, `@mcp.resource(uri)`, `.run(transport="stdio")`, and
`.streamable_http_app(transport_security=, max_request_body_size=)`.

**`TransportSecuritySettings` is unchanged**; `mcp/server/transport_security.py` only
gained `DEFAULT_MAX_REQUEST_BODY_SIZE` and a `RequestBodyLimitMiddleware`.
`mcp/client/streamable_http.py` and `mcp/shared/memory.py` — the two modules the tests
import — are **byte-identical** between 2.0.0 and 2.1.1.

### Internal imports: none to migrate

The phase anticipated removing reliance on non-public SDK paths. There was none to
remove. All four import sites already use documented public paths:

| Site | Import | Status |
|---|---|---|
| `mcp/__init__.py` | `from mcp.server.mcpserver import MCPServer` | Public — the migration guide names this exact line |
| `mcp/http.py` | `from mcp.server.transport_security import TransportSecuritySettings` | Public, unchanged in 2.1.1 |
| `tests/test_mcp_http.py` | `from mcp.client.streamable_http import streamable_http_client` | Public, byte-identical |
| `tests/test_mcp_stdio.py` | `from mcp.shared.memory import create_client_server_memory_streams` | Public, byte-identical |

Imports were therefore **not** mechanically rewritten. One import was **added**, below.

### The one real behavior change (and the defect it caused)

2.1.1 introduces an error taxonomy in `mcp.server.mcpserver.exceptions`: `ToolError`
(anticipated failure — message reaches the caller, logged at INFO without a traceback)
versus everything else (treated as a crash — message replaced with
`Error executing tool <name>`, traceback logged at ERROR).

Under 2.0.0 `call_tool` passed `str(e)` through for **every** exception. Under 2.1.1
this runtime's typed `ModelValidationError` — which is by definition an *anticipated*
caller-input failure — was being misclassified as a server crash. Effect: a malformed
`context_snapshot` still failed closed (INV-CTX-043 held), but the caller was no longer
told *what* was wrong, and a caller's bad input was logged as a server crash.

This was caught by `tests/integration/test_context_native_compilation.py::
test_the_mcp_surface_fails_closed_on_a_malformed_snapshot`, which asserts the failure
message names `context_snapshot`. The test was **not** weakened.

**Fix (exposure boundary only):** `_compile()` in `src/l9_cognitive_runtime/mcp/__init__.py`
translates `ModelValidationError` into the SDK's public `ToolError`. This is strictly
*narrower* than the 2.0.0 surface — only this runtime's typed anticipated-failure class
is surfaced to callers; genuine bugs (`TypeError`, `KeyError`, …) are now correctly
classified as crashes and withheld, which 2.0.0 did not do.

Scope discipline held: no compiler stage was touched. `CompilePipeline`, the compiler
models, `service.py`, and `parse_context_snapshot`'s own raised type are unchanged —
`parse_context_snapshot` still raises `InvalidValueError`, as its direct tests require.

## Deliberately NOT changed (recorded, not fixed)

1. **Resource-path error classification.** `RunNotFoundError` subclasses this repo's
   `ModelValidationError`, not the SDK's `ResourceError`, so an unknown/expired/
   cross-principal run read is classified by 2.1.1 as an unexpected resource error:
   the client gets a generic message naming only the URI (anti-enumeration **preserved**,
   verified live), but the server now logs a traceback at ERROR where 2.0.0 did not.
   Mapping it to the SDK's `ResourceNotFoundError` would change the wire code from
   `-32603` to `-32602`. The phase contract says `preserve_resources_and_run_store_behavior`,
   so this is left alone and recorded here as a known log-noise consequence.
2. **Deeper compile failures other than `ModelValidationError`** now return the generic
   crash message rather than 2.0.0's pass-through text. This is the SDK's intended
   hardening and no contract or test requires the old behavior.

## Validation evidence

Every command below was executed in this session; results are as printed.

| Command | Result |
|---|---|
| `uv sync --extra dev --frozen` | mcp 2.0.0 → 2.1.1, mcp-types 2.0.0 → 2.1.1 |
| `uv run --no-sync ruff check src tests` | All checks passed! |
| `uv run --no-sync ruff format --check src tests` | 77 files already formatted |
| `uv run --no-sync mypy src tests` (strict) | Success: no issues found in 77 source files |
| `uv run --no-sync python -m pytest -q` (Python 3.11.15) | **364 passed** |
| `uv run --no-sync python -m pytest -q` (Python 3.12.11) | **364 passed** |
| `uv run --no-sync python -m build` | built sdist + wheel |
| `uv run --no-sync python runtime/kernel_pipeline/run_validators.py` | pack status `passed`, 7/7 validators passed |
| `git status --porcelain` after build | only the 3 intended files; no `dist/` artifacts |

Baseline was captured on unmodified `main` first (364 passed, ruff/mypy clean, 7/7
validators) so the single failure above is attributable to the upgrade and nothing else.

### Live MCP smoke (host process, Streamable HTTP, mcp 2.1.1)

Deployment pack built via `l9_cognitive_runtime.deployment` and verified by
`PackLoader` (`manifest_digest 19da8e857c7bcd39fb06f191c3b60f0e2f895fe7af3e60ac2429854949e73c18`),
served over Streamable HTTP at `/v1/mcp`:

| Check | Result |
|---|---|
| `GET /healthz` | `{"status":"ok","transport":"streamable_http"}` |
| `GET /readyz` | 5 read-only tools listed |
| `initialize` | `l9-cognitive-runtime 0.1.0` |
| `tools/list` | exactly the 5 read-only tools — surface unchanged |
| `tools/call runtime_capabilities` | `mode=read_only writes=False execution=False context_snapshot_input=True` |
| `tools/call plan_kernel_activation` (governed snapshot) | context consumed, `context_digest=8d1622d240170ddf…`, 11 kernels |
| `tools/call compile_runtime` (plain vs governed) | context digests `cad7ca61…` vs `8292a77f…` — governed context moves compiled-context identity |
| packet assertions | `compiled_task_context` present; `compiled_task_context_digest == digests.context == provenance.context_digest` |
| malformed snapshot | `is_error=True`, message names `context_snapshot` — fail-closed **and** diagnosable |
| `resources/list`, `resources/read` | `l9://runtime/version`, `l9://runtime/capabilities` read OK |
| unknown run resource | rejected, generic message naming only the URI — anti-enumeration preserved |
| clean session shutdown | sessions exited without error |

### Cross-surface semantic equivalence

Direct Python, the CLI, and MCP over Streamable HTTP produce **identical digests** for
the same mission — all eight (`intent`, `execution`, `graph`, `handoff`, `context`,
`manifest`, `validation`, `semantic`). The spine converges.

## Remaining UNKNOWNs

- **Container image smoke — UNKNOWN.** No Docker daemon is available in this execution
  environment (`/var/run/docker.sock` absent). The image-level assertions —
  `docker build`, non-root `10001:10001`, `--read-only` rootfs, `--cap-drop=ALL` —
  were **not** executed here and are **not** claimed. The semantic core of that
  workflow (real `initialize` + real `compile_runtime` with a governed
  `ContextSnapshot` over Streamable HTTP) *was* executed against a live server, as
  tabled above, but against a host process rather than the container image.
  `container-smoke.yml` triggers on pull requests touching `pyproject.toml`, `uv.lock`
  and `src/**` — all three are in this change — so CI supplies the image evidence.
- **Repository governance PR gate — UNKNOWN** until a hosted run completes.

## Rollback

Revert the single commit. It touches three files and adds no new dependency; reverting
restores `mcp>=2.0.0` and the 2.0.0/2.0.0 lock entries. The `ToolError` translation is
inert on 2.0.0 in the sense that it changes only which exception type carries the same
message, so a partial revert is not required.

## Next-phase handoff (Phase 2 — MCP-011 hosted auth)

- `mcp.server.auth` is present in 2.1.1 (`provider.py`, `routes.py`, `settings.py`,
  `handlers/`, `middleware/`). `mcp/server/auth/routes.py` is one of the modules that
  changed between 2.0.0 and 2.1.1 — read it before designing the resource-server wiring.
- `mcp.server.mcpserver` publicly exports `authenticated_principal`,
  `RequestStateSecurity`, `RequestStateBoundary`, `RequestStateCodec` and
  `AESGCMRequestStateCodec`. These are the SDK's principal-binding seam and are the
  first thing to evaluate before writing bespoke middleware.
- The hosted principal seam already exists in this repo and is documented as pre-auth:
  `run_store.py` binds runs to a caller-supplied principal string, and
  `mcp/__init__.py` pins `LOCAL_PRINCIPAL = "local-stdio"` with a comment naming
  MCP-011C. Phase 2 must bind the hosted principal to the validated token subject and
  must not let `LOCAL_PRINCIPAL` reach hosted traffic.
- `mcp/http.py` already documents that it performs and claims **no** authentication.
  That docstring must change with the code.

## Update — container evidence now exists (CI, PR #45)

`container-smoke.yml` ran on `53555be` and **passed in full** ([run](https://github.com/Quantum-L9/l9-cognitive-runtime/actions/runs/33575188006)): *Build
immutable candidate image* (including its `Config.User == 10001:10001` assertion), *Run
hardened container* (`--read-only`, `--cap-drop=ALL`, `no-new-privileges`), *Health and
readiness*, and *Real MCP initialize and compile* — the governed `ContextSnapshot` smoke
with its packet and provenance digest assertions, against the deployed container on
mcp 2.1.1.

This supersedes the "container image — UNKNOWN" entry above for everything **except a
published immutable digest**: that workflow builds a local tag, so no registry digest
exists and none is claimed. Publishing one still requires `release-staging`, which
remains blocked (`FINAL_FINDINGS-RELEASE-STAGING.md`).
