# ADR (required) — OAuth resource-server architecture for MCP-011

**Status:** BLOCKED — human decision required before 011A/B/C implementation claims completeness  
**Contract:** L9CR-MCP-PR-REMEDIATION-001 / phase_8  
**Date:** 2026-08-06

## Decision required before code

| Topic | Options (examples) | Chosen |
|-------|--------------------|--------|
| Authorization server | Auth0 / Okta / Keycloak / GitHub OIDC / custom AS | **UNDECIDED** |
| Issuer URL | Real HTTPS issuer | **UNDECIDED** |
| Resource audience | Exact `https://<staging-host>/v1/mcp` | **UNDECIDED** (must not be `runtime.example`) |
| Signing algorithm | RS256 / ES256 (HS256 test-only forbidden in prod) | **UNDECIDED** |
| JWKS distribution | AS JWKS URI; cache + key rotation | **UNDECIDED** |
| Client registration | CIMD / preregistration / DCR | **UNDECIDED** |
| PKCE | Required for public clients | Required (proposed) |
| Refresh-token ownership | AS-owned; MCP never stores refresh tokens | Proposed |
| Revocation | Fail closed on AS unavailable (503) | Proposed |

## Prohibited (already violated by source PR #12)

- Hardcoded `https://auth.example` / `https://runtime.example`
- Production dependence on test HMAC secrets
- Accepting GitHub tokens as MCP bearer tokens
- Helper-only JWT validation not wired to `/v1/mcp`

## Stop condition

Complete discovery and local stdio work, but **stop before claiming hosted authentication** until this ADR is filled by an authorized human and 011A/B/C are rewritten against it.
