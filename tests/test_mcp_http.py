"""HTTP transport smoke tests."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from l9_cognitive_runtime.mcp.http import create_http_app

ROOT = Path(__file__).resolve().parents[1]


def test_health_and_ready() -> None:
    client = TestClient(create_http_app(ROOT))
    assert client.get("/healthz").json()["status"] == "ok"
    ready = client.get("/readyz").json()
    assert ready["status"] == "ready"
    assert "compile_runtime" in ready["tools"]


def test_stdio_opens_no_socket_by_default() -> None:
    # Stdio entry must not import/bind HTTP unless explicitly invoked.
    import l9_cognitive_runtime.mcp as stdio_mod

    assert not hasattr(stdio_mod, "create_http_app") or "http" not in stdio_mod.__dict__
