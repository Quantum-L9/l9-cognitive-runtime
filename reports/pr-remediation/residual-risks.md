# Residual risks — L9CR-MCP-PR-REMEDIATION-001

## Human decisions required (blockers)

1. **OAuth authorization server selection** — issuer, JWKS distribution, client registration (CIMD/DCR/prereg), PKCE, refresh ownership, revocation. Stop condition: do not claim hosted authentication until chosen.
2. **Real staging hostname + TLS** — required before enabling hosted client configs (MCP-013) and staging deployment evidence (MCP-012).
3. **Independent OAuth security reviewers (2)** — required before merging 011A/B/C.
4. **Human client certifications** — Claude Code and Cursor; approver must not be the implementation agent.

## Technical residual risk

| Area | Risk | Level |
|------|------|-------|
| Fail-closed parsing | Synthesis still on stack tip | High until MCP-005 replaced |
| Hosted MCP | Unauthenticated /v1/mcp through PR12 tip | Critical until 011B wired |
| Principal spoofing | Client-supplied principal on runs | High until 011C |
| Placeholder URLs | Example domains in auth + client configs | High if mistaken for prod |
| Optional PR16 | GitHub token trust surface | Paused — do not merge |
| Evidence quality | GMP reports claim complete without command artifacts | Medium — replace with Phase 13 schema |

## What is NOT claimed

- Production ready
- OAuth complete / agent-wide hosted access
- Staging TLS endpoint exists
- Client certifications passed
