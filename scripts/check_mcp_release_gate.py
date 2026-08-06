#!/usr/bin/env python3
"""Validate MCP release metadata completeness (blocking gate, L9CR-MCP-014)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_TOOLS = {
    "runtime_capabilities",
    "compile_runtime",
    "get_bundle_digests",
    "list_pack_manifest",
    "validate_pack_path",
    "get_run",
    "runtime_render",
}

REQUIRED_FIELDS = (
    "release_id",
    "git_sha",
    "image_digest",
    "rollback",
    "tool_registry",
    "client_certifications",
)


def validate(meta: dict) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in meta:
            errors.append(f"missing field: {key}")
    rollback = meta.get("rollback") or {}
    if not rollback.get("image_digest"):
        errors.append("rollback.image_digest required")
    if not rollback.get("identifier"):
        errors.append("rollback.identifier required")
    tools = set(meta.get("tool_registry") or [])
    if tools != REQUIRED_TOOLS:
        errors.append(f"tool_registry must equal read-only set; got {sorted(tools)}")
    certs = meta.get("client_certifications") or {}
    for client in ("claude_code", "cursor"):
        entry = certs.get(client) or {}
        if entry.get("status") != "pass":
            errors.append(f"client_certifications.{client}.status must be pass")
        if not entry.get("operator") or not entry.get("certified_at"):
            errors.append(f"client_certifications.{client} needs operator + certified_at")
    digest = str(meta.get("image_digest") or "")
    if not digest.startswith("sha256:") or len(digest) < 15:
        errors.append("image_digest must be sha256:…")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    args = parser.parse_args(argv)
    meta = json.loads(args.metadata.read_text(encoding="utf-8"))
    errors = validate(meta)
    if errors:
        print(f"FAIL {args.metadata}")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"PASS {args.metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
