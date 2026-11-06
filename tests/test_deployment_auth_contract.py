# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_test_deployment_auth_contract__py
# title: test deployment auth contract
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/test_deployment_auth_contract.py
# content_hash: 170642bc19a64e55bb58ce535c162ed8f3b25a7eaa10338ad403453caeeece54
# token_cost_estimate: 359
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Hosted MCP deployment authentication contract checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".l9" / "deployment.yaml"
HOST = "mcp-staging.quantumaipartners.com"
RESOURCE_URL = f"https://{HOST}/v1/mcp"


def _profile() -> dict[str, Any]:
    raw = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast("dict[str, Any]", raw)


def test_hosted_profile_requires_auth_before_public_ingress_starts() -> None:
    profile = _profile()
    env = profile["runtime"]["environment"]

    ingress = profile["targets"]["staging"]["ingress"]
    assert ingress["mode"] == "caddy"
    assert ingress["hostnames"] == [HOST]
    assert env["L9_ALLOWED_HOSTS"] == HOST
    assert env["L9_REQUIRE_AUTH"] == "true"
    assert env["L9_MCP_RESOURCE_URL"] == RESOURCE_URL


def test_identity_provider_configuration_remains_deploy_rendered() -> None:
    profile = _profile()
    env = profile["runtime"]["environment"]

    assert profile["secrets"]["authority"] == "infisical"
    assert profile["secrets"]["runtime_mode"] == "deploy_render"
    # Issuer/audience are deployment facts supplied by the real identity
    # provider. Do not invent or commit them merely to make the profile start.
    assert "L9_OAUTH_ISSUER" not in env
    assert "L9_OAUTH_AUDIENCE" not in env
