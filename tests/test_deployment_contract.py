"""Static deployment/release contract checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".l9/deployment.yaml"
RELEASE = ROOT / ".github/workflows/release-staging.yml"
CORE_RELEASE_CHANNEL = "v2"
# Core v2 commit pinned by release-staging.yml container-release.
CONTAINER_RELEASE_SHA = "450f6ec753435365c6e4212cc898ee9ba560bb7d"
HOST = "mcp-staging.quantumaipartners.com"


def _profile() -> dict[str, Any]:
    raw = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast("dict[str, Any]", raw)


def test_deployment_profile_binds_staging_mcp_contract() -> None:
    profile = _profile()
    assert profile["schema"] == "l9.deployment-profile/v1"
    assert profile["project"]["repository"] == "Quantum-L9/l9-cognitive-runtime"
    assert profile["project"]["runtime_profile"] == "container-service"
    assert profile["artifact"]["image"] == "ghcr.io/quantum-l9/l9-cognitive-runtime"
    assert profile["artifact"]["require_digest"] is True
    assert profile["runtime"]["container_port"] == 8080
    assert profile["runtime"]["user"] == "non_root"
    assert profile["runtime"]["read_only_root_filesystem"] is True
    assert profile["runtime"]["environment"]["L9_ALLOWED_HOSTS"] == HOST
    assert profile["health"]["startup"]["path"] == "/readyz"
    assert profile["health"]["post_deploy"]["path"] == "/readyz"
    assert profile["network"]["public_ingress"]["hostnames"] == [HOST]
    assert profile["network"]["public_ingress"]["tls"] == "automatic"


def _core_uses(workflow: dict[str, Any]) -> list[str]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    uses: list[str] = []
    analysis = jobs["analysis"]
    assert isinstance(analysis, dict)
    analysis_uses = analysis.get("uses")
    if isinstance(analysis_uses, str) and analysis_uses.startswith("Quantum-L9/l9-ci-core/"):
        uses.append(analysis_uses)
    release = jobs["release"]
    assert isinstance(release, dict)
    for step in release.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_uses = step.get("uses")
        if isinstance(step_uses, str) and step_uses.startswith("Quantum-L9/l9-ci-core/"):
            uses.append(step_uses)
    return uses


def test_release_workflow_is_manual_pinned_and_source_bound() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    workflow = yaml.safe_load(text)
    assert isinstance(workflow, dict)
    assert _core_uses(workflow) == [
        f"Quantum-L9/l9-ci-core/.github/workflows/analyze-semgrep.yml@{CORE_RELEASE_CHANNEL}",
        f"Quantum-L9/l9-ci-core/.github/actions/container-release@{CONTAINER_RELEASE_SHA}",
    ]
    assert "profile: release" in text
    assert "event: release" in text
    assert "matrix-id: release-semgrep" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "source-revision-build-arg-name: L9_SOURCE_REVISION" in text
    assert (
        "registered-profile-path: integrations/consumers/"
        "l9-cognitive-runtime.deployment.yaml" in text
    )
    assert "DEPLOYMENT_BROKER_TOKEN" in text
