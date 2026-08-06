"""Static policy checks for the production container baseline (L9CR-MCP-012)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
OPS = (ROOT / "docs/ops/container-deploy.md").read_text(encoding="utf-8")
SCAN = (ROOT / ".github/workflows/container-scan.yml").read_text(encoding="utf-8")


def test_dockerfile_is_multistage_non_root() -> None:
    assert "AS builder" in DOCKERFILE
    assert "AS runtime" in DOCKERFILE
    assert "USER 10001:10001" in DOCKERFILE
    assert "HEALTHCHECK" in DOCKERFILE
    assert '"l9_cognitive_runtime.mcp.http"' in DOCKERFILE
    assert "\nUSER root" not in DOCKERFILE and "\nUSER 0" not in DOCKERFILE


def test_dockerfile_has_no_secret_literals() -> None:
    lowered = DOCKERFILE.lower()
    for needle in ("api_key", "private_key", "begin rsa", "aws_secret", "password="):
        assert needle not in lowered


def test_ops_doc_covers_digest_and_rollback() -> None:
    assert "digest" in OPS.lower()
    assert "rollback" in OPS.lower()
    assert "--read-only" in OPS
    assert "/healthz" in OPS


def test_scan_workflow_enforces_policy() -> None:
    assert "trivy" in SCAN.lower()
    assert "HIGH,CRITICAL" in SCAN
    assert "10001:10001" in SCAN
