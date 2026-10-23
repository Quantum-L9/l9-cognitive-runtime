"""Static deployment/release contract checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".l9/deployment.yaml"
RELEASE = ROOT / ".github/workflows/release-staging.yml"
# Immutable Core revision carrying the blocking policy and strict release profile.
CORE_RELEASE_CHANNEL = "edf799046023f44dae3bb8aad9aa91247124706b"
# Core commit pinned by release-staging.yml container-release (l9-ci-core #225).
CONTAINER_RELEASE_SHA = "89c9bc4e5ceafab932c92a2fdca2d3739fccf95f"
HOST = "mcp-staging.quantumaipartners.com"


def _profile() -> dict[str, Any]:
    raw = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast("dict[str, Any]", raw)


def test_deployment_profile_binds_staging_mcp_contract() -> None:
    profile = _profile()
    # l9-deploy accepts only l9.deployment-profile/v2.
    assert profile["schema"] == "l9.deployment-profile/v2"
    assert profile["project"]["repository"] == "Quantum-L9/l9-cognitive-runtime"
    assert profile["project"]["runtime_profile"] == "container-service"
    assert profile["artifact"]["image"] == "ghcr.io/quantum-l9/l9-cognitive-runtime"
    assert profile["runtime"]["container_port"] == 8080
    assert profile["runtime"]["user"] == "non_root"
    assert profile["runtime"]["read_only_root_filesystem"] is True
    assert profile["runtime"]["environment"]["L9_ALLOWED_HOSTS"] == HOST
    assert profile["health"]["startup"]["path"] == "/readyz"
    assert profile["health"]["post_deploy"]["path"] == "/readyz"
    assert profile["secrets"]["project_slug"] == "l9-cognitive-runtime"


def test_staging_target_is_c1_without_changing_its_runtime() -> None:
    staging = _profile()["targets"]["staging"]
    assert staging["server"]["address"] == "46.62.243.82"
    assert staging["server"]["ssh"] == {"user": "root", "port": 22}
    assert staging["server"]["host_key"].startswith("ssh-ed25519 ")
    # C1 is shared and protected: verify its Docker, never manage it.
    assert staging["host"] == {"docker": "verify", "backup_tools": "none"}
    assert staging["ingress"]["mode"] == "caddy"
    assert staging["ingress"]["hostnames"] == [HOST]
    assert staging["ingress"]["host_port"] == 18080
    assert staging["allowed_source_refs"] == ["refs/heads/main"]
    assert staging["secrets_environment"] == "staging"


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
    analysis = workflow["jobs"]["analysis"]
    assert isinstance(analysis, dict)
    analysis_with = analysis.get("with")
    assert isinstance(analysis_with, dict)
    assert analysis_with.get("profile") == "release"
    assert analysis_with.get("event") == "release"
    assert analysis_with.get("matrix-id") == "release-semgrep"
    assert "profile: release" in text
    assert "matrix-id: release-semgrep" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "source-revision-build-arg-name: L9_SOURCE_REVISION" in text
    # l9.deployment-request/v2 fixes the profile path; Core #225 dropped the input.
    assert "registered-profile-path" not in text
    assert "deployment-profile: .l9/deployment.yaml" in text
    assert "deployment-broker-token: ${{ secrets.GH_TOKEN }}" in text


def test_release_profile_allows_core_dispatch_nightly_class() -> None:
    """Core analyze-semgrep@v2 remaps workflow_dispatch to event class nightly."""
    pack = json.loads((ROOT / ".github/governance/execution-profiles.yaml").read_text())
    release = pack["profiles"]["release"]
    assert release["sdk_profile"] == "ci_deep"
    assert release["strict"] is True
    assert release["default_mode"] == "blocking"
    assert release["providers"] == ["semgrep"]
    assert "nightly" in release["allowed_events"]
    assert "workflow_dispatch" in release["allowed_events"]
