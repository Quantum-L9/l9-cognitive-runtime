# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_test_container_release_pin__py
# title: test container release pin
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/test_container_release_pin.py
# content_hash: df112169f868afa30758039540fcc5baf0aa1835b7f68b706a00d81857e1792e
# token_cost_estimate: 213
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Release-staging must pin the Core container-release action to a full SHA."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-staging.yml"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(r"uses:\s+Quantum-L9/l9-ci-core/\.github/actions/container-release@(\S+)")


def test_container_release_action_is_sha_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = USES_RE.search(text)
    assert match is not None, "container-release uses: missing from release-staging.yml"
    gitref = match.group(1).split("#", 1)[0].strip().strip("'\"")
    assert SHA_RE.match(gitref), (
        "container-release must be pinned to a 40-character commit SHA, "
        f"not a mutable tag: {gitref!r}"
    )
