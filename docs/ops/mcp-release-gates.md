# MCP production release gates (L9CR-MCP-014)

Blocking checklist. Any failed gate stops promotion.

## Automated (CI)

1. `pr-check` green (ruff, pytest, build, MCP secret scan).
2. `container-scan` green when image inputs change.
3. Conformance suite: `pytest tests/conformance -q` (protocol parity, OAuth, isolation, read-only registry).
4. `python scripts/check_mcp_release_gate.py release/mcp-release-metadata.json` exit 0.

## Manual

1. Claude Code certification recorded (`docs/ops/mcp-client-certification.md`).
2. Cursor certification recorded.
3. Image digest + rollback digest present in metadata.
4. Tool registry diff reviewed: only `READ_ONLY_TOOLS` entries.

## Release metadata

Copy `release/mcp-release-metadata.example.json` → `release/mcp-release-metadata.json` (local/release artifact; do not commit secrets). Required fields are enforced by `check_mcp_release_gate.py`.

## Rollback identifier

Use `rollback.image_digest` (previous known-good `@sha256:…`) from metadata. Procedure: `docs/ops/container-deploy.md`.
