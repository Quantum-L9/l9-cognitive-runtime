# ChatGPT MCP deployment and connection

Status: deployment baseline for the existing read-only MCP surface. Hosted OAuth is not implemented by this change and must not be claimed.

## Endpoint

The container serves:

- MCP: `/v1/mcp`
- liveness: `/healthz`
- readiness: `/readyz`

The image binds on `0.0.0.0:8080`. MCP host validation remains fail-closed: a remote deployment must set `L9_ALLOWED_HOSTS` to the exact external host value(s) accepted by the ingress path.

## Build

Build from an exact Git commit. The full source SHA is mandatory and is embedded into the deployment pack manifest.

```bash
SOURCE_REVISION="$(git rev-parse HEAD)"
docker build \
  --build-arg L9_SOURCE_REVISION="$SOURCE_REVISION" \
  -t l9-cognitive-runtime-mcp:"${SOURCE_REVISION:0:12}" \
  .
```

The build does not trust or rewrite the mutable repository-root `MANIFEST.json`. It creates `/opt/l9-pack` from the canonical execution, validation, and handoff contracts; the activated kernels; and the contract schemas. That pack receives a new manifest and is verified with `PackLoader` during the image build.

## Local container smoke

```bash
docker run --rm \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  -p 8080:8080 \
  -e L9_ALLOWED_HOSTS="127.0.0.1,127.0.0.1:8080,localhost,localhost:8080" \
  l9-cognitive-runtime-mcp:"${SOURCE_REVISION:0:12}"
```

Verify:

```bash
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/readyz
```

## First ChatGPT smoke

ChatGPT connects to remote MCP servers, not directly to a local-only server. For the first private proof, use OpenAI Secure MCP Tunnel or an equivalent private staging route rather than publishing this unauthenticated endpoint to the public internet.

Current OpenAI Developer Mode flow:

1. Enable Developer Mode for the workspace/account allowed to create custom apps.
2. In ChatGPT web, open Settings or Workspace Settings -> Apps -> Create.
3. Enter the reachable MCP endpoint ending in `/v1/mcp`.
4. Use no authentication only for the bounded private smoke environment.
5. Select **Scan Tools**.
6. Verify the scan discovers the existing read-only tool surface and no unexpected actions.
7. Create the app as a draft and test `runtime_capabilities` plus one compile/validate path.

OpenAI currently states that `search` and `fetch` are not required for a custom MCP server. They remain out of this connection-critical path.

Reference: https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt

## Production boundary

Do not expose the current unauthenticated `/v1/mcp` as a public production service.

Before production publication, complete a separate hosted-auth contract that provides:

- a real OAuth/OIDC authorization server and issuer
- exact resource audience for the deployed HTTPS MCP endpoint
- asymmetric token validation through issuer/JWKS metadata
- bearer enforcement on `/v1/mcp`
- standards-compliant protected-resource discovery / authentication challenge
- authenticated principal binding for run ownership
- HTTP-level auth and cross-principal tests
- refresh-token/offline-access compatibility required by the chosen provider and ChatGPT flow

No placeholder issuer, audience, hostname, or test HMAC key is acceptable in production configuration.

## Acceptance for this deployment baseline

This slice is complete only when CI proves all of the following from a clean checkout:

- deployment pack is deterministic
- deployment pack verifies through `PackLoader`
- runtime compiles against the deployment pack
- MCP resources for kernel/schema aliases resolve
- image builds from a full Git SHA
- container runs as UID/GID `10001:10001`
- container runs read-only with dropped Linux capabilities
- `/healthz` and `/readyz` succeed
- a real Streamable HTTP MCP initialize succeeds against the running container
- the discovered tool set exactly matches `READ_ONLY_TOOLS`
- `runtime_capabilities` succeeds over the container network boundary
