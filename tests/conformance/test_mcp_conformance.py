"""Cross-client MCP protocol / OAuth / isolation conformance (L9CR-MCP-014)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import jwt
import pytest
from starlette.testclient import TestClient

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server
from l9_cognitive_runtime.mcp.auth import (
    PROTECTED_RESOURCE_METADATA,
    AuditLog,
    require_scope,
    validate_bearer_jwt,
)
from l9_cognitive_runtime.mcp.http import create_http_app
from l9_cognitive_runtime.mcp.run_store import InMemoryRunStore
from l9_cognitive_runtime.models.errors import InvalidValueError

ROOT = Path(__file__).resolve().parents[2]
AUDIENCE = "https://runtime.example/v1/mcp"
MUTATING_NAMES = frozenset(
    {
        "write_",
        "delete_",
        "execute_",
        "mutate_",
        "apply_",
        "deploy_",
    }
)


@pytest.fixture(autouse=True)
def _jwt_hmac_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "L9_TEST_JWT_HMAC",
        "".join(("test-", "hmac-key-", "not-for-production-", "use-32b")),
    )


def _hmac() -> str:
    return os.environ["L9_TEST_JWT_HMAC"]


def _token(**claims: object) -> str:
    payload = {
        "sub": "cert-user",
        "aud": AUDIENCE,
        "exp": time.time() + 60,
        "scope": "runtime:compile runtime:read runtime:capabilities",
        **claims,
    }
    return jwt.encode(payload, _hmac(), algorithm="HS256")


def test_protocol_stdio_and_http_tool_parity() -> None:
    stdio_tools = set(build_server(ROOT)._tool_manager._tools.keys())  # noqa: SLF001
    ready = TestClient(create_http_app(ROOT)).get("/readyz").json()["tools"]
    assert stdio_tools == set(ready)
    assert set(READ_ONLY_TOOLS) == stdio_tools


def test_only_read_only_tools_registered() -> None:
    names = set(build_server(ROOT)._tool_manager._tools.keys())  # noqa: SLF001
    assert names == set(READ_ONLY_TOOLS)
    for name in names:
        assert not any(name.startswith(prefix) for prefix in MUTATING_NAMES)


def test_oauth_audience_and_expiry_gates() -> None:
    ok = validate_bearer_jwt(_token(), audience=AUDIENCE, secret=_hmac())
    assert ok.subject == "cert-user"
    with pytest.raises(InvalidValueError):
        validate_bearer_jwt(_token(aud="https://evil.example"), audience=AUDIENCE, secret=_hmac())
    with pytest.raises(InvalidValueError):
        validate_bearer_jwt(_token(exp=time.time() - 5), audience=AUDIENCE, secret=_hmac())


def test_oauth_scope_allow_deny_audit() -> None:
    principal = validate_bearer_jwt(_token(), audience=AUDIENCE, secret=_hmac())
    audit = AuditLog()
    require_scope(principal, "runtime_capabilities", audit)
    assert audit.events[-1]["allowed"] is True
    limited = validate_bearer_jwt(
        _token(scope="runtime:read"),
        audience=AUDIENCE,
        secret=_hmac(),
    )
    with pytest.raises(InvalidValueError):
        require_scope(limited, "compile_runtime", audit)
    assert audit.events[-1]["allowed"] is False


def test_cross_principal_run_isolation() -> None:
    store = InMemoryRunStore()
    alice = store.create("alice", {"mission": "a"})
    bob = store.create("bob", {"mission": "b"})
    assert store.get(alice.run_id, "alice") is not None
    assert store.get(alice.run_id, "bob") is None
    assert store.get(bob.run_id, "alice") is None
    assert store.list_for_principal("alice") == [alice]


def test_protected_resource_metadata_lists_scopes() -> None:
    scopes = set(PROTECTED_RESOURCE_METADATA["scopes_supported"])
    assert {
        "runtime:compile",
        "runtime:read",
        "runtime:capabilities",
        "runtime:render",
    } <= scopes
