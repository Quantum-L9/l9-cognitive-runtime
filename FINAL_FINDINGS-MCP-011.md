# FINAL FINDINGS — MCP-011: hosted OAuth/OIDC protection

Phase 2 of `l9cr_straight_line_chatgpt_mcp_deploy` v1.0.0.

## Architecture boundary

Authentication terminates at the HTTP ingress and establishes principal identity.
Nothing below it knows authentication exists.

```
ChatGPT --Bearer--> Starlette ingress (mcp/http.py)
   |  SDK AuthenticationMiddleware -> BearerAuthBackend -> JwtTokenVerifier  (mcp/auth.py)
   |  SDK RequireAuthMiddleware    -> 401 / 403 + WWW-Authenticate
   |  SDK AuthContextMiddleware    -> validated AccessToken in request context
   v
 MCPServer tools/resources -> principal binding for run ownership only
   v
 CognitiveRuntimeService -> CompilePipeline    <- auth-agnostic, unchanged
```

`src/l9_cognitive_runtime/mcp/auth.py` is the **entire** authentication surface. It
imports nothing from `l9_cognitive_runtime` — enforced by a test, not by convention.
`CompilePipeline`, the compiler models, kernel runtime, execution graph, adapter
renderer, `ContextSnapshot` and `CognitiveRuntimeService` are untouched by this phase.

## Authentication flow

1. ChatGPT calls `/v1/mcp` with no token.
2. The SDK returns **401** with
   `WWW-Authenticate: Bearer error="invalid_token", …, resource_metadata="https://<host>/.well-known/oauth-protected-resource/v1/mcp"`.
3. ChatGPT fetches that RFC 9728 document, learns the authorization server, and runs
   its OAuth flow against the **issuer** — never against this runtime.
4. ChatGPT retries with a bearer JWT. `JwtTokenVerifier` validates it and returns an
   SDK `AccessToken`; the request proceeds.

Validation performed, each independently exercised by a negative test:

| Check | Failure |
|---|---|
| Signature against the issuer's JWKS (`kid` lookup, cached 300s) | 401 |
| `iss` equals the configured issuer | 401 |
| `aud` equals the configured audience | 401 |
| `exp` in the future (`exp` is *required*) | 401 |
| `nbf` in the past when present | 401 |
| Algorithm on the asymmetric allowlist | 401 |
| Token attributable to a principal (`client_id`/`azp`/`sub`) | 401 |
| Required scopes present (when configured) | 403 `insufficient_scope` |

**Symmetric and unsigned algorithms are refused at configuration time**, not merely
absent from the default: `HostedAuthConfig` raises on any `HS*` or `none` entry, so a
deployment cannot opt into the JWT confusion attack where a published *public* key is
used as an HMAC secret. A hand-assembled HS256-over-public-PEM token is proven rejected
(PyJWT refuses to even mint one, so the test builds it byte by byte to exercise *this*
validator rather than PyJWT's encoder).

## Principal binding

The hosted principal is the SDK's own `principal_components(token)` triple —
`(client_id, issuer, subject)` — the same components the SDK binds session ownership
to. Two users of one OAuth client are therefore distinct principals, and a subject is
only ever compared within the issuer that vouched for it.

`LOCAL_PRINCIPAL` (`"local-stdio"`) never reaches hosted traffic. Under hosted auth a
request without a validated token resolves to `None`, not to the local principal:
tools raise `ToolError`, and run resources raise `RunNotFoundError` (anti-enumerating).
`RequireAuthMiddleware` should already have rejected such a request; this is the second
lock on the same door.

**Read-only is preserved.** Authentication buys identity, never new verbs — the
capability surface still reports `mode=read_only`, `writes=false`, `execution=false`,
asserted under a valid token.

## Negative test matrix — `tests/test_mcp_auth.py` (24 tests, all passing)

| Requirement | Test | Result |
|---|---|---|
| no token rejected | `test_missing_token_is_challenged` | 401 + `WWW-Authenticate` + `resource_metadata=` |
| malformed token rejected | `test_malformed_token_rejected`, `test_invalid_token_is_rejected_over_http` | pass |
| expired token rejected | `test_expired_token_rejected` | pass |
| not-yet-valid rejected | `test_not_yet_valid_token_rejected` | pass |
| wrong issuer rejected | `test_wrong_issuer_rejected` | pass |
| wrong audience rejected | `test_wrong_audience_rejected` | pass |
| invalid signature rejected | `test_invalid_signature_rejected` | pass |
| algorithm confusion rejected | `test_algorithm_confusion_token_rejected` | pass |
| symmetric/`none` refused | `test_symmetric_and_unsigned_algorithms_are_refused_by_configuration` | pass |
| unattributable token rejected | `test_unattributable_token_rejected` | pass |
| valid token accepted | `test_valid_token_accepted`, `test_valid_token_reaches_the_tools_and_capabilities_advertise_protection` | pass |
| principal bound to validated identity | `test_runs_are_owned_by_the_validated_principal_and_isolated_between_them` | pass |
| principal A cannot read principal B's run | same test | pass |
| cross-principal and unknown-run are anti-enumerating | same test (error shapes compared) | identical |
| stdio remains unauthenticated | `test_stdio_remains_unauthenticated_and_locally_owned` | pass, `authentication="none"` |
| compiler output identical with/without wrapper | `test_authentication_does_not_change_what_the_compiler_produces` | digests equal |
| auth module imports no compiler stage | `test_auth_module_does_not_import_any_compiler_stage_owner` | pass |
| no compiler stage imports auth | `test_no_compiler_stage_owner_imports_auth` | pass |
| CompilePipeline is auth-agnostic | `test_compile_pipeline_is_auth_agnostic` | pass |
| health leaks no token claims | `test_health_endpoints_stay_open_and_leak_no_identity` | pass |
| context snapshot still fails closed | existing `test_the_mcp_surface_fails_closed_on_a_malformed_snapshot` | pass |
| partial config fails loudly | `test_partial_configuration_fails_loudly_rather_than_downgrading` | pass |
| `L9_REQUIRE_AUTH` refuses unprotected start | `test_require_auth_refuses_to_start_unprotected` | pass |

### The isolation test was mutation-checked

A passing isolation test proves nothing unless it can fail. `_principal()` was
temporarily replaced with `return LOCAL_PRINCIPAL` and the suite re-run:
`test_runs_are_owned_by_the_validated_principal_and_isolated_between_them` **failed**
(user-b read user-a's run), and passed again on restore. The assertion discriminates.

## Live evidence (real socket, `L9_REQUIRE_AUTH=true`)

| Request | Observed |
|---|---|
| `GET /healthz` | `200 {"status":"ok","transport":"streamable_http"}` — open, no identity |
| `POST /v1/mcp` no token | `401` + `WWW-Authenticate: Bearer error="invalid_token", error_description="Authentication required", resource_metadata="https://runtime.example.com/.well-known/oauth-protected-resource/v1/mcp"` |
| `POST /v1/mcp` garbage token | `401` |
| `GET /.well-known/oauth-protected-resource/v1/mcp` | `200 {"resource":"https://runtime.example.com/v1/mcp","authorization_servers":["https://issuer.example.com/"],"bearer_methods_supported":["header"]}` |

### A defect found and fixed in the wiring

The SDK registers the RFC 9728 route at an **absolute** path derived from
`resource_server_url`. This repo mounts the MCP app under `/v1`, so the route would
only have answered at `/v1/.well-known/oauth-protected-resource/v1/mcp` — a location no
client looks at, and *not* the one the SDK's own `WWW-Authenticate` header advertises.
Discovery would have dead-ended. `create_http_app` now lifts the SDK's own route object
(handler included, so the document is not re-implemented) onto the parent app root. The
live check above confirms the advertised path and the served path now agree.

## Secret handling

**No credential material exists in this repository, and none is needed.** A resource
server validates tokens with the issuer's *public* keys, so there is no client secret,
signing key, or bearer token to hold — that is a property of the design, not an
omission. Configuration is variable *names* only:

| Variable | Meaning |
|---|---|
| `L9_OAUTH_ISSUER` | Authorization server issuer identifier |
| `L9_OAUTH_AUDIENCE` | Expected `aud` — this resource server's identifier |
| `L9_MCP_RESOURCE_URL` | Public MCP endpoint URL (drives RFC 9728 metadata) |
| `L9_OAUTH_JWKS_URI` | Optional; discovered from the issuer when absent |
| `L9_OAUTH_REQUIRED_SCOPES` | Optional, comma-separated |
| `L9_OAUTH_ALGORITHMS` | Optional; asymmetric only, `HS*`/`none` refused |
| `L9_REQUIRE_AUTH` | `true` ⇒ refuse to start unprotected |

Partial configuration is an error, never a silent downgrade: a deployment that sets an
issuer but forgets the audience would otherwise accept tokens minted for someone else.

## Deliberate decisions, recorded

1. **`INV-CTX-041` was honored, not amended.** `mcp/auth.py` imports `jwt` and
   `anyio`. Declaring them in `[project.dependencies]` broke
   `test_no_new_runtime_dependency_was_added`, which pins the runtime set to
   `{mcp, pydantic, PyYAML}`. INV-CTX-041 permits change only where "repository law
   explicitly requires otherwise", and an agent is not repository law
   (`CLAUDE.md` rung 7). The declarations were **reverted** rather than the test
   weakened — the contract's stop condition for exactly this case. Both packages are
   hard requirements of `mcp` itself and are pinned in `uv.lock` (`pyjwt 2.13.0`,
   `anyio 4.14.2`), so the installed closure does not grow by one package. **Residual
   risk, stated plainly:** if a future `mcp` release drops either, `import jwt` fails
   loudly in CI rather than silently degrading. If the operator prefers explicit
   declaration, that is a one-line INVARIANTS.md amendment plus the test — an owner
   decision, not mine.
2. **HTTP serves unprotected when no OAuth configuration is present.** Making auth
   unconditional would break `container-smoke.yml` and the existing HTTP tests, which
   run the transport with no issuer. `L9_REQUIRE_AUTH=true` is the operator's assertion
   switch and **must be set on the hosted deployment**; without it a misconfigured
   deployment comes up open. `main()` also prints an explicit warning to stderr when
   serving unprotected. This is the known gap in "protected by default".
3. **`authorization_servers` is emitted with a trailing slash**
   (`https://issuer.example.com/`) by pydantic `AnyHttpUrl` normalization, while
   RFC 8414 issuer comparison is exact string comparison. Not this repository's code —
   the SDK's metadata model — and not observed to break discovery, but recorded
   because a strict client could care.

## Validation evidence

| Command | Result |
|---|---|
| `uv sync --extra dev --frozen` | clean; lock unchanged (no dependency added) |
| `uv run --no-sync ruff check src tests` | All checks passed! |
| `uv run --no-sync ruff format --check src tests` | 79 files already formatted |
| `uv run --no-sync mypy src tests` (strict) | Success: no issues found in 79 source files |
| `uv run --no-sync python -m pytest -q` (Python 3.11.15) | **388 passed** (364 pre-existing + 24 new) |
| `uv run --no-sync python -m pytest -q` (Python 3.12.11) | **388 passed** |
| `uv run --no-sync python -m build` | built sdist + wheel |
| `uv run --no-sync python runtime/kernel_pipeline/run_validators.py` | pack `passed`, 7/7 validators |
| live socket checks | tabled above |

No pre-existing test was modified. No assertion was weakened.

## Remaining UNKNOWNs

- **Issuer, audience, client registration and scopes — UNKNOWN.** No identity provider
  is named anywhere in this repository (verified by `git grep` across tracked files),
  so none was hard-coded. These are deployment-supplied.
- **Whether the chosen provider supports the registration mode ChatGPT needs — UNKNOWN.**
  Per OpenAI's developer-mode documentation, ChatGPT supports static credentials, Client
  ID Metadata Documents (CIMD) when the authorization server advertises it, and Dynamic
  Client Registration when configured. Which applies cannot be determined without the
  provider.
- **Container and hosted-deployment behavior — UNKNOWN.** No Docker daemon in this
  environment; see the Phase 1 findings.
- **Scope enforcement is implemented but unexercised end-to-end**: `required_scopes`
  flows to the SDK's `RequireAuthMiddleware`, whose 403 path is SDK code with SDK tests.
  This phase adds no 403 test of its own because no scope policy is configured.

## Rollback

Revert the commit. `mcp/auth.py` and `tests/test_mcp_auth.py` are new files; the
changes to `mcp/__init__.py` and `mcp/http.py` are additive and default to the previous
unauthenticated posture when `token_verifier`/`auth_settings` are `None`. No dependency
or lock change to unwind.

## Next-phase handoff (Phase 3 — private ChatGPT deployment)

- Deploy with `L9_REQUIRE_AUTH=true` and the four OAuth variables set. Without it the
  hosted endpoint is open, and finding #2 above is the failure mode.
- `L9_MCP_RESOURCE_URL` must be the **public** MCP URL as ChatGPT will call it, and
  `L9_OAUTH_AUDIENCE` must be what the issuer stamps into `aud`. A mismatch presents as
  a uniform 401 with no diagnostic — the verifier deliberately logs only the exception
  class, never the token or its claims.
- `L9_ALLOWED_HOSTS` must include the public host, or DNS-rebinding protection refuses
  the request before auth is reached.
- ChatGPT developer mode requires a Business/Enterprise/Edu workspace and an
  admin/owner to create the app and run **Scan Tools**; app creation and the OAuth
  consent are human actions the agent cannot perform.
