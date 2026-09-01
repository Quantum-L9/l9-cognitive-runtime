# FINAL DEPLOYMENT BRIEF

`l9cr_straight_line_chatgpt_mcp_deploy` v1.0.0 — terminal handoff.

## Executive verdict: BLOCKED

Not `CHATGPT_MCP_DEPLOYMENT_PROVEN`. Two of four phases are complete and green; the
remaining two are stopped by blockers that are named, reproduced, and attributed.

| Phase | Verdict | One line |
|---|---|---|
| 1 — MCP SDK 2.1.1 | **PASS** | Frozen at 2.1.1, all surfaces proven, one real behavior regression found and fixed |
| 2 — Hosted OAuth/OIDC | **PASS** | Resource-server protection at ingress; compiler untouched; 26 auth tests, mutation-checked |
| 3 — Private ChatGPT smoke | **HUMAN_BOUNDARY** | Runtime answers the full sequence under real auth; no container runtime, no OpenAI tunnel credential, no ChatGPT admin access |
| 4 — Release-staging | **BLOCKED** | Upstream `l9-ci-core` wiring gap makes the release gate unpassable by construction |

The overall verdict is **BLOCKED**, not HUMAN_BOUNDARY: Phase 4 is a real technical
defect, not merely an absent human. It is upstream and not fixable from this repository.

## State

| Field | Value |
|---|---|
| `origin/main` | `28f5b4b2450299de34f2d2d69bea32ece09363b1` (unchanged — nothing merged) |
| Work branch | `claude/l9-chatgpt-mcp-deploy-vpevgd` |
| Head | `989d3526472800688887f1c1488ed912bbf98ea5` |
| Merged PRs | **none** — see "Deviation from the contract" |
| MCP SDK | `mcp==2.1.1`, `mcp-types==2.1.1` (locked, frozen) |
| Deployed image digest | **UNKNOWN — no image was built** |
| Sealed pack manifest digest | `19da8e857c7bcd39fb06f191c3b60f0e2f895fe7af3e60ac2429854949e73c18` |
| Private ChatGPT smoke | **UNKNOWN** — ChatGPT never called this runtime |
| Release-staging | **FAILING** — reproduced 2026-09-01 |

Four commits, each green before push:

```
989d352  fix(mcp): stop a log message tripping semgrep's credential-leak rule
955128d  fix(mcp): refuse token key material over plaintext HTTP
37a04db  feat(mcp): protect hosted MCP with OAuth/OIDC
ae8c3eb  chore(mcp): upgrade runtime SDK to 2.1.1
```

## Auth architecture (one paragraph)

Bearer JWTs are validated at the HTTP ingress — signature against the issuer's JWKS,
then `iss`, `aud`, `exp`, `nbf` — and the SDK's `(client_id, issuer, subject)` triple
becomes the principal that owns a run. Symmetric and unsigned algorithms are refused at
configuration time; key material is refused over plaintext HTTP except to loopback.
`mcp/auth.py` imports nothing from `l9_cognitive_runtime`, no compiler stage imports it,
and `CompilePipeline` contains no auth concept — all three asserted by tests. A compiled
bundle is digest-identical with and without a token. stdio is untouched: unauthenticated,
owned by `local-stdio`, and unreachable from hosted traffic. No credential material
exists in the repository, because a resource server validates with public keys and has
none to hold.

## Validation commands and results

Run on this branch's head, Python 3.11.15 and 3.12.11:

| Command | Result |
|---|---|
| `uv sync --extra dev --frozen` | clean; `mcp 2.1.1` |
| `uv run --no-sync ruff check src tests` | All checks passed! |
| `uv run --no-sync ruff format --check src tests` | 79 files already formatted |
| `uv run --no-sync mypy src tests` (strict) | Success: no issues found in 79 source files |
| `uv run --no-sync python -m pytest -q` | **390 passed** (364 baseline + 26 new) — both interpreters |
| `uv run --no-sync python -m build` | sdist + wheel; tree clean afterwards |
| `uv run --no-sync python runtime/kernel_pipeline/run_validators.py` | pack `passed`, 7/7 validators |
| `semgrep scan --config p/python` (CI pin 1.171.0) | **0 findings** — matches pre-change baseline |
| `container-smoke.yml` image assertions | **NOT RUN — no Docker daemon** |

A baseline was captured on unmodified `main` **first** (364 passed, clean, 7/7), so
every failure encountered afterwards is attributable to the change that caused it.

### Live evidence, authenticated, over a real socket

Sealed pack + `L9_REQUIRE_AUTH=true` + real RSA keypair + real JWKS + real RS256 tokens:

- `initialize` → `l9-cognitive-runtime 0.1.0`; `tools/list` → exactly five read-only tools
- `runtime_capabilities` → `mode=read_only writes=False execution=False authentication=oauth2_bearer`
- `plan_kernel_activation` (governed snapshot) → `context_digest=8d1622d240170ddf…`, 11 kernels
- `compile_runtime` → `run_id`, `semantic=e64cb433…`, `manifest=19da8e85…`,
  `execution_packet.compiled_task_context_digest == digests.context == provenance.context_digest`
- plan and compile agree on context identity; a governed snapshot moves it (`cad7ca61…` → `8292a77f…`)
- no token → `401` + `WWW-Authenticate` with the RFC 9728 pointer; wrong scope → `403 insufficient_scope`
- `/.well-known/oauth-protected-resource/v1/mcp` served at the advertised root path
- direct Python, CLI and MCP produce **identical digests** across all eight

## What was found that nobody had asked for

1. **MCP 2.1.1 silently degraded a fail-closed path.** Its new error taxonomy
   reclassified this runtime's typed validation error as a server crash, so a malformed
   `context_snapshot` still failed closed but stopped saying *what* was wrong. Caught by
   an existing test, fixed at the exposure boundary — not by weakening the test.
2. **The RFC 9728 discovery route would have dead-ended.** The SDK registers it at an
   absolute path; this app mounts MCP under `/v1`, so the document would have answered
   only where nothing looks — including where the SDK's own `WWW-Authenticate` header
   points. `tunnel-client` fetches exactly this document on startup and treats
   `authorization_servers` from it as its only source of truth, so the tunnel would have
   failed discovery. Fixed by lifting the SDK's own route to the app root.
3. **The staging profile would deploy an unauthenticated MCP endpoint to the public
   internet.** `.l9/deployment.yaml` sets `public_ingress.enabled: true` on
   `mcp-staging.quantumaipartners.com` and carries no OAuth variables. Not modified —
   it is an infrastructure manifest and that is an operator decision. Exact change below.
4. **The release gate is unpassable for every consumer of this pipeline**, not just this
   repo. See Phase 4.

## Deviation from the contract, stated plainly

The contract specifies one PR per phase, each merged before the next branches from
`main`. The session directive assigns a single branch,
`claude/l9-chatgpt-mcp-deploy-vpevgd`, and forbids pushing elsewhere; merge authority is
not held here either. The phases were therefore executed sequentially as four commits on
that one branch, and **no PR was opened** (none was requested). `main` is unchanged, so
Phase 3's "exact current main SHA" requirement is unmet by construction: the deployment
would have had to be built from a revision that does not contain the auth work.

## Remaining UNKNOWNs

- **Image digest, SBOM, provenance** — no container runtime here; and Phase 4 shows the
  release path cannot publish one anyway.
- **ChatGPT invocation** — no OpenAI tunnel credential, no ChatGPT workspace admin.
  No claim is made that ChatGPT called this runtime.
- **Issuer / audience / client registration** — no identity provider is named anywhere
  in the repository, so none was invented. The live proof used a locally generated
  issuer; that validates the validator, not a production trust anchor.
- **Staging liveness** — a hostname in a manifest is not a service. No request was made.
- **Whether a newer `l9-ci-core` pin fixes Phase 4** — Core `main` still does not pass
  `identity-map`, so a pin bump looks insufficient, but that was not proven by running.

## Next actions, in dependency order

**1 — Unblock the release gate (upstream, `Quantum-L9/l9-ci-core`).** Nothing else in
this list can complete first. Add an `identity-map` output to `resolve-governance` and
pass it from `analyze-semgrep.yml` to `invoke-sdk` (which already accepts it), or
package the map in the SDK. Add a `sdk-contract-check` case that drives a
consumer-shaped repo with ≥1 finding through `analyze-semgrep.yml` at `profile: release`
— Core's current self-test passes `--identity-map` explicitly, which is exactly why it
never caught this. Do **not** "fix" it by pointing `sdk_policy` at an advisory-default
policy: that turns the release gate green by making findings non-blocking.

**2 — Review and merge this branch.** `main` must carry the auth work before any
deployment is built from it.

**3 — Close the unauthenticated-ingress gap** in `.l9/deployment.yaml` under
`runtime.environment`:

```yaml
    L9_REQUIRE_AUTH: "true"
    L9_OAUTH_ISSUER: <authorization server issuer>               # UNKNOWN
    L9_OAUTH_AUDIENCE: <the aud your issuer stamps for this RS>  # UNKNOWN
    L9_MCP_RESOURCE_URL: https://mcp-staging.quantumaipartners.com/v1/mcp
```

With Secure MCP Tunnel, also set `network.public_ingress.enabled: false` — the tunnel is
outbound-only and needs no inbound hostname. None of these are secrets.

**4 — Run Secure MCP Tunnel** (`github.com/openai/tunnel-client`) as a sidecar or on a
host with private reach to the service. Needs an OpenAI API key with **Tunnels Read +
Use** (`CONTROL_PLANE_API_KEY`), a `CONTROL_PLANE_TUNNEL_ID`, and outbound HTTPS to
`api.openai.com:443`.

**5 — Create the ChatGPT app.** Developer mode → Apps → Create → Connection: **Tunnel** →
select the tunnel → complete OAuth → **Scan Tools**. Requires a Business/Enterprise/Edu
workspace and an admin/owner. Platform *Tunnels* permission and ChatGPT *developer mode*
are separate grants and having one does not confer the other — the documented
most-common blocker.

**6 — Re-run the three-tool sequence from ChatGPT itself.** Only that turns Phase 3 from
HUMAN_BOUNDARY to PROVEN, and this brief from BLOCKED to PASS.

## Artifacts

- `FINAL_FINDINGS-MCP-SDK-2.1.1.md`
- `FINAL_FINDINGS-MCP-011.md`
- `FINAL_FINDINGS-PRIVATE-CHATGPT-MCP-SMOKE.md`
- `FINAL_FINDINGS-RELEASE-STAGING.md`
