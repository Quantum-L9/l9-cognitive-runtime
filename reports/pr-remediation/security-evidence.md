# Security evidence — L9CR-MCP-PR-REMEDIATION-001

## Phase 0–1 static review (this session)

Method: code-level audit of PR diffs (not a penetration test). Skills: `l9-auditing-security`, contract `L9CR-MCP-PR-REMEDIATION-001`.

### Secrets / static credentials
- No static bearer tokens found in PR 2–17 diffs.
- PR14 secret scanner present and blocks Authorization/Bearer patterns in configs.
- PR12 test HMAC sourced from env (acceptable for tests only).

### Auth / authz
- **Critical:** PR12 `auth.py` helpers are not imported by `mcp/http.py`. `/v1/mcp` remains open.
- No `WWW-Authenticate` / protected-resource discovery route.
- Hardcoded `https://runtime.example` / `https://auth.example` in `PROTECTED_RESOURCE_METADATA`.
- HS256 helper with caller-supplied secret; no JWKS/issuer config path for production.

### Injection / path
- PR4 CLI `--write-dir` unconfined (Sonar S8707).
- Pack loader path confinement present; symlink escape test missing; service swallows pack load failures.

### Data exposure
- AuditLog redacts keys `token`/`authorization`/`secret` only (shallow) — insufficient vs recursive redaction requirements in 011C.
- Health endpoints in PR11 appear free of credentials (to be re-verified after auth wiring).

### Automated scans observed on PRs
- Semgrep: SUCCESS on open PRs (snapshot 2026-08-06).
- SonarCloud FAILURE on PRs 4, 8, 13, 14, 15.
- SonarCloud SUCCESS does **not** prove protocol correctness (contract rule).

### Commands still required (not yet executed this phase)
- Repository secret scanner (gitleaks/trufflehog)
- pip-audit / uv audit
- Container scan (after MCP-012 repair)
- Full pytest/ruff/mypy/build on clean remediation branches
