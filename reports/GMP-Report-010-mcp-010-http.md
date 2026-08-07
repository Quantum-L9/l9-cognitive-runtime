# Evidence Report — MCP-010 Streamable HTTP transport

- **contract_id:** L9CR-MCP-PR-REMEDIATION-001 / logical contract MCP-010
- **replacement_branch:** `rem/mcp-010`
- **base:** `rem/mcp-009`
- **supersedes source PR:** #11 (`feat/mcp-010`, safety tag `backup/pr-11-e2a7f374`)
- **primary concern:** standards-compliant, bounded HTTP transport — **no authentication claimed**

## Endpoint & routes

`/v1/mcp` (Streamable HTTP, mounted so the SDK's `/mcp` resolves under `/v1`),
plus `/healthz` and `/readyz`. The legacy SSE transport is **not** mounted
(`test_no_legacy_sse_route`). A separate console entry point
`l9-cognitive-runtime-http` is added (distinct from the stdio script).

## Phase-1 remediations applied (F-PR11-CONTROLS)

The source had no size/origin/timeout/concurrency limits and no HTTP initialize
test. This PR adds them all:

| Control | Implementation | Test |
|---|---|---|
| Request size ≤ 1 MiB | `MaxBodySizeMiddleware` + SDK `max_request_body_size` | `test_oversized_request_rejected` → 413 |
| Origin allowlist, CORS off by default | `OriginAllowlistMiddleware` (empty default) | `test_disallowed_origin_rejected` → 403; `test_allowed_origin_passes` |
| Concurrency limit (8) | `ConcurrencyLimitMiddleware` (semaphore, sheds with 503) | `test_concurrency_limit_sheds_load` |
| Timeout (60s default) | `RequestTimeoutMiddleware` | `test_request_timeout_returns_504` |
| Bind 127.0.0.1 | `L9_BIND_HOST` default `127.0.0.1` | — |
| Trusted proxies only | uvicorn `proxy_headers` off unless `L9_TRUST_PROXY=true`, `forwarded_allow_ips` | — |
| DNS-rebinding protection | `TransportSecuritySettings(allowed_hosts=…)` | exercised by the wire test |

## Contract acceptance (phase_7)

| Requirement | Evidence |
|---|---|
| HTTP MCP initialize succeeds | `test_http_initialize_and_tool_parity` — real in-process `initialize` → `tools/list` → `tools/call` over ASGI |
| Tool surface exactly matches stdio | `test_tool_surface_matches_stdio` + wire `tools/list` == `READ_ONLY_TOOLS` |
| Oversized requests fail | `test_oversized_request_rejected` (413) |
| Disallowed origins fail | `test_disallowed_origin_rejected` (403) |
| Concurrency limits enforced | `test_concurrency_limit_sheds_load` (503) |
| No authentication-completion claim | module docstring + health payloads carry no principal/credential (`test_health_and_ready`); no local-dev identity bypass |

## Commands executed (this branch head)

```
uv sync --extra dev --frozen   # locked (CI parity)
uv run ruff check .            # All checks passed!
uv run ruff format --check .   # 38 files already formatted
uv run mypy src                # Success: no issues found in 16 source files
uv run python -m pytest -q     # 87 passed
uv run python -m build         # Successfully built sdist + wheel
```

## Residual / deviations

- Health responses expose only `{status, transport}` and the readiness tool list
  (no principal/credential data).
- Live TLS staging deployment + hosted OAuth are **out of scope** here and gated
  on MCP-011/012 (human-provided issuer + staging hostname). This transport makes
  no auth claim and enables no identity bypass.
