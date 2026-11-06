---
id: "l9-cognitive-runtime.context.reports_gmp_report_012_chatgpt_deploy_baseline__md"
title: "GMP Report 012 chatgpt deploy baseline"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "reports/GMP-Report-012-chatgpt-deploy-baseline.md"
content_hash: "a517308cc8bcd26531dbd90b8400357232a3c21f9f22cec1d3c6f5cdab79d6be"
token_cost_estimate: 428
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "meta_kernel_forge"
description: "Unknown"
activation_signals: ["kernel"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
# Evidence Report — ChatGPT MCP deployment baseline

- **scope:** deployment packaging and real container-network MCP smoke
- **base:** `main@b318ceb6ab4b72c070260fdceb99ebbe082a9c7e`
- **branch:** `feat/chatgpt-mcp-deploy-baseline`
- **tool surface:** unchanged
- **authentication claim:** none

## Changes

- Added deterministic deployment-pack builder that ignores the stale repository-root manifest and seals only canonical contracts, activated kernels, and schemas.
- Added MCP-facing kernel/schema aliases while preserving canonical source paths in manifest metadata.
- Added non-root, read-only-compatible container baseline.
- Added container CI that performs health/readiness plus a real Streamable HTTP `initialize -> tools/list -> tools/call` against the running container.
- Added ChatGPT connection runbook for private smoke and the explicit production-auth boundary.

## Security invariants

- Source revision must be a full 40-character Git SHA.
- Deployment pack destination cannot be the repository or a child of it.
- Source paths are confined beneath the repository root.
- Alias collisions fail closed.
- `PackLoader` verifies the built deployment pack before the image advances to the runtime stage.
- Runtime image is non-root (`10001:10001`).
- CI runs the container read-only, with `no-new-privileges` and all Linux capabilities dropped.
- Remote MCP host allowlisting remains explicit through `L9_ALLOWED_HOSTS`.

## Not claimed

- OAuth/OIDC complete
- public production readiness
- live TLS hostname
- ChatGPT draft app created
- human ChatGPT client certification complete

Those remain later connection gates and require real deployment/auth coordinates rather than placeholders.
