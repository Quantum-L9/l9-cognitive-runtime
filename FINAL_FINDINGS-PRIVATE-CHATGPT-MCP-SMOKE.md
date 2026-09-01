# FINAL FINDINGS — private ChatGPT MCP deployment smoke

Phase 3 of `l9cr_straight_line_chatgpt_mcp_deploy` v1.0.0.

## Verdict: HUMAN_BOUNDARY

The runtime is proven to answer ChatGPT's exact call sequence, under real OAuth
protection, over a real socket. It is **not** proven to have been called *by ChatGPT*,
and no image digest is claimed. Three separate blockers stand between here and PROVEN,
each requiring a credential or an account action this agent does not have. They are
named exactly, below.

Nothing in this document describes a deployment that happened. Where a required piece
of evidence could not be produced, it is marked UNKNOWN rather than approximated.

## Exact revision and pack

| Field | Value |
|---|---|
| Source revision under test | `989d3526472800688887f1c1488ed912bbf98ea5` (branch `claude/l9-chatgpt-mcp-deploy-vpevgd`) |
| `origin/main` | `28f5b4b2450299de34f2d2d69bea32ece09363b1` — the phase work is **not** merged |
| Deployment pack manifest digest | `19da8e857c7bcd39fb06f191c3b60f0e2f895fe7af3e60ac2429854949e73c18` |
| Pack build | `python -m l9_cognitive_runtime.deployment --source-root . --destination <pack> --source-revision <sha>`, then verified by `PackLoader().load(...)` |
| **Image digest** | **UNKNOWN — no image was built** |

## Why no image: no container runtime

`/var/run/docker.sock` does not exist in this execution environment; `docker version`
reports the daemon unreachable. The Dockerfile's own guarantees — `USER 10001:10001`,
`--read-only` root filesystem, `--cap-drop=ALL`, the sealed `/opt/l9-pack` built from
`L9_SOURCE_REVISION` — were therefore **not executed and are not claimed**. A mutable
tag would not substitute for a digest even if one existed.

`container-smoke.yml` builds and asserts exactly these properties in CI and triggers on
changes to `pyproject.toml`, `uv.lock` and `src/**` — all touched by this work — so the
image evidence is available from a pull request, not from this session.

## What *was* proven: the runtime answers the ChatGPT call sequence, protected

A live server was started from the sealed pack with hosted auth enforced
(`L9_REQUIRE_AUTH=true`, `L9_OAUTH_REQUIRED_SCOPES=l9.compile`), a real RSA keypair, a
real JWKS endpoint, and real RS256 bearer tokens minted against it. Every call below
crossed a socket and a validated `Authorization: Bearer` header.

### Pre-flight

| Check | Observed |
|---|---|
| `POST /v1/mcp` with no token | `401` |
| `GET /.well-known/oauth-protected-resource/v1/mcp` | `{"resource":"https://runtime.l9.test/v1/mcp","authorization_servers":["https://issuer.l9.test/"],"scopes_supported":["l9.compile"],"bearer_methods_supported":["header"]}` |

That document matters more than it looks: `tunnel-client` fetches OAuth Protected
Resource Metadata from the MCP server on startup, and its README states that
`authorization_servers` from that document is **the only source of truth** for
auth-server handling. Without the Phase 2 route fix it would have 404'd.

### The required three-tool sequence

Governed `ContextSnapshot` fixture: one provenance-backed
`architecture_constraint` (`multiple_workers`, `governed_authoritative`, global scope,
immutable coordinate `review-multiple-workers`) — not an empty object.

| Step | Tool | Result |
|---|---|---|
| — | `initialize` | `l9-cognitive-runtime 0.1.0` |
| — | `tools/list` | exactly the five read-only tools |
| 1 | `runtime_capabilities` | `server=l9-cognitive-runtime version=0.1.0 mode=read_only writes=False execution=False authentication=oauth2_bearer context_snapshot_input=True` |
| 2 | `plan_kernel_activation` | context consumed — `context_digest=8d1622d240170ddf21372ed0…`, 11 kernels, 4-step sequence |
| 3 | `compile_runtime` | `run_id=ghMuRFThJ_zz7UyarsVX2A`; `semantic=e64cb433e9120676…`, `context=8d1622d240170ddf…`, `manifest=19da8e857c7bcd39…` |

Assertions that passed inside step 3:

- `execution_packet.compiled_task_context` is present and non-empty;
- `execution_packet.compiled_task_context_digest == digests.context`;
- `execution_packet.provenance.context_digest == digests.context`;
- `digests.manifest` present and equal to the sealed pack's manifest digest;
- `plan_kernel_activation` and `compile_runtime` agree on `context_digest` for the same
  governed input — the two surfaces derive one context identity, not two.

Separately, on the unauthenticated local run, the same governed snapshot moved compiled
context identity away from the ungoverned compile (`cad7ca61…` → `8292a77f…`), proving
the fixture is *material* rather than merely accepted.

### Negative control

| Request | Observed |
|---|---|
| Valid signature, correct issuer/audience, **wrong scope** | `403` + `WWW-Authenticate: Bearer error="insufficient_scope", error_description="Required scope: l9.compile"` |

This closes the one gap Phase 2 left open: scope enforcement is now exercised
end-to-end rather than assumed from SDK code.

## Deployment topology — and a defect in the current profile

Intended: `ChatGPT → OpenAI-hosted tunnel endpoint ← tunnel-client ← private MCP server`,
outbound-only HTTPS from the tunnel host to `api.openai.com:443`, no inbound firewall
rule, MCP server never on the public internet.

`.l9/deployment.yaml` as committed does **not** describe that topology, and this is the
single most important finding in this phase:

```yaml
network:
  public_ingress:
    enabled: true
    hostnames: [mcp-staging.quantumaipartners.com]
    tls: automatic
runtime:
  environment:
    L9_ALLOWED_HOSTS: mcp-staging.quantumaipartners.com
```

It carries **no** `L9_OAUTH_ISSUER`, `L9_OAUTH_AUDIENCE`, `L9_MCP_RESOURCE_URL` or
`L9_REQUIRE_AUTH`. Deployed as written against current `main`, staging would publish the
MCP endpoint on the public internet **with no authentication at all** — the precise
outcome this contract forbids (`expose_remote_MCP_endpoint_without_public_unauthenticated_ingress`),
and the failure mode Phase 2 finding #2 warned about.

**This file was deliberately not modified.** It is a deployment/infrastructure manifest,
and infrastructure changes require explicit human approval rather than an agent's
judgement. The required change is stated below as an operator action, not applied.

## Remaining human actions

Each is blocked on a credential or account permission unavailable here. None is a
technical unknown.

**1. Close the unauthenticated-ingress gap** — add to `.l9/deployment.yaml` under
`runtime.environment`:

```yaml
    L9_REQUIRE_AUTH: "true"
    L9_OAUTH_ISSUER: <your authorization server issuer>          # UNKNOWN
    L9_OAUTH_AUDIENCE: <the aud your issuer stamps for this RS>  # UNKNOWN
    L9_MCP_RESOURCE_URL: https://mcp-staging.quantumaipartners.com/v1/mcp
```

`L9_REQUIRE_AUTH=true` makes an unprotected start a hard failure, so a missing variable
stops the deployment instead of opening the endpoint. With Secure MCP Tunnel,
`network.public_ingress.enabled` should also go to `false` — the tunnel is outbound-only
and needs no inbound hostname. None of these are secrets; the issuer and audience are
public identifiers.

**2. Run Secure MCP Tunnel** (`github.com/openai/tunnel-client`), as a sidecar in the
same Pod or on a host that can reach the service privately:

- requires an OpenAI API key with **Tunnels Read + Use** exported as
  `CONTROL_PLANE_API_KEY`, and a `CONTROL_PLANE_TUNNEL_ID`;
- requires outbound HTTPS to `api.openai.com:443` (or `mtls.api.openai.com:443` under
  control-plane mTLS);
- point its MCP binding at the private `/v1/mcp` URL and keep the daemon healthy
  (`/healthz`, `/readyz`, `/metrics`, `/ui`) for the whole ChatGPT session — connector
  discovery and every subsequent call go through it.

**3. Create the ChatGPT app** — Settings → Security and login → enable Developer mode,
then Apps → Create, choose **Tunnel** under Connection, select the tunnel (or paste the
`tunnel_id`), complete the OAuth authorization prompt, and run **Scan Tools**.

Two permission grants are involved and having one does not confer the other: platform
**Tunnels Read + Use**, and ChatGPT **developer mode**, which is limited to
Business/Enterprise/Edu workspaces and to admins/owners. This split is the documented
most-common setup blocker. If the tunnel does not appear in ChatGPT, it is associated
with a Platform organization rather than the target ChatGPT workspace.

Then re-run the three-tool sequence above from ChatGPT itself. Only that turns this
phase's verdict from HUMAN_BOUNDARY to PROVEN.

## Unresolved UNKNOWNs

- **Image digest, SBOM, provenance attestation — UNKNOWN.** No container runtime here.
- **ChatGPT connection — UNKNOWN.** No OpenAI tunnel credential; no ChatGPT workspace
  admin access. No claim is made that ChatGPT invoked this runtime.
- **Issuer and audience — UNKNOWN.** No identity provider is named anywhere in the
  repository, so none was invented. The live proof above used a locally generated
  issuer and keypair; that demonstrates the validator, not the production trust anchor.
- **Staging hostname liveness — UNKNOWN.** `mcp-staging.quantumaipartners.com` appears
  in a manifest. A hostname in a manifest is not a running service, and no request to it
  was made or is reported.

## Next-phase handoff

Phase 4 established that the release path cannot currently publish an image at all —
the canonical gate fails before the publish step — so the missing image digest above is
downstream of that defect, not an independent gap. See
`FINAL_FINDINGS-RELEASE-STAGING.md`.
