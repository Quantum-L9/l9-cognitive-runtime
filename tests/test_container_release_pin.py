"""Release-staging must pin the Core container-release action to a full SHA."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-staging.yml"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(
    r"uses:\s+Quantum-L9/l9-ci-core/\.github/actions/container-release@(\S+)"
)


def test_container_release_action_is_sha_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = USES_RE.search(text)
    assert match is not None, "container-release uses: missing from release-staging.yml"
    gitref = match.group(1).split("#", 1)[0].strip().strip("'\"")
    assert SHA_RE.match(gitref), (
        "container-release must be pinned to a 40-character commit SHA, "
        f"not a mutable tag: {gitref!r}"
    )
