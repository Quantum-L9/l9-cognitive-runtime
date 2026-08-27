#!/usr/bin/env python3
"""Load ops/autonomy/surface_profile.yaml for SessionStart / projectors / tests.

SessionStart must work with bare `python3` (no venv, no PyYAML). Block extractors
are stdlib-only. Full mapping load uses PyYAML when available.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

PROFILE_REL = Path("ops/autonomy/surface_profile.yaml")


def governance_root() -> Path:
    return Path.home() / ".cursor-governance"


def profile_path(root: Path | None = None) -> Path:
    return (root or governance_root()) / PROFILE_REL


def _extract_block_scalar(text: str, key: str) -> str:
    """Extract a YAML literal block scalar (`key: |`) without PyYAML.

    Continues through blank lines; stops at the next non-empty, non-indented line.
    """
    lines = text.splitlines()
    header = re.compile(rf"^{re.escape(key)}:\s*\|\s*$")
    start = None
    for i, line in enumerate(lines):
        if header.match(line):
            start = i + 1
            break
    if start is None:
        return ""

    body: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            body.append("")
            continue
        if line[0] not in " \t":
            break
        body.append(line)
    while body and body[-1] == "":
        body.pop()
    if not body:
        return ""
    indents = [len(ln) - len(ln.lstrip(" ")) for ln in body if ln.strip()]
    indent = min(indents) if indents else 0
    dedented = [(ln[indent:] if len(ln) >= indent else ln) for ln in body]
    return "\n".join(dedented).rstrip() + "\n"


def session_start_block(root: Path | None = None) -> str:
    text = profile_path(root).read_text(encoding="utf-8")
    return _extract_block_scalar(text, "session_start_block")


def llm_rules_override(root: Path | None = None) -> str:
    text = profile_path(root).read_text(encoding="utf-8")
    return _extract_block_scalar(text, "llm_rules_override")


def load_profile(root: Path | None = None) -> dict[str, Any]:
    path = profile_path(root)
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML required for load_profile(); use session_start_block() on SessionStart"
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"surface profile must be a mapping: {path}")
    return data


def block_sha256(root: Path | None = None) -> str:
    return hashlib.sha256(session_start_block(root).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.stdout.write(session_start_block(root))
