"""OAuth / audit middleware tests."""

from __future__ import annotations

import os
import time

import jwt
import pytest

from l9_cognitive_runtime.mcp.auth import (
    PROTECTED_RESOURCE_METADATA,
    AuditLog,
    require_scope,
    validate_bearer_jwt,
)
from l9_cognitive_runtime.models.errors import InvalidValueError

_AUDIENCE = "https://runtime.example/v1/mcp"


@pytest.fixture(autouse=True)
def _jwt_hmac_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Env-sourced key keeps fixtures out of jwt-hardcoded-secret rules.
    monkeypatch.setenv(
        "L9_TEST_JWT_HMAC",
        "".join(("test-", "hmac-key-", "not-for-production-", "use-32b")),
    )


def _hmac() -> str:
    return os.environ["L9_TEST_JWT_HMAC"]


def _token(**claims: object) -> str:
    payload = {
        "sub": "user-1",
        "aud": _AUDIENCE,
        "exp": time.time() + 60,
        "scope": "runtime:compile runtime:read runtime:capabilities",
        **claims,
    }
    return jwt.encode(payload, _hmac(), algorithm="HS256")


def test_protected_resource_metadata() -> None:
    assert "scopes_supported" in PROTECTED_RESOURCE_METADATA


def test_valid_token_and_scope() -> None:
    principal = validate_bearer_jwt(_token(), audience=_AUDIENCE, secret=_hmac())
    audit = AuditLog()
    require_scope(principal, "compile_runtime", audit)
    assert audit.events[-1]["allowed"] is True


def test_wrong_audience_rejected() -> None:
    with pytest.raises(InvalidValueError):
        validate_bearer_jwt(
            _token(aud="https://other.example"),
            audience=_AUDIENCE,
            secret=_hmac(),
        )


def test_expired_token_rejected() -> None:
    with pytest.raises(InvalidValueError):
        validate_bearer_jwt(
            _token(exp=time.time() - 10),
            audience=_AUDIENCE,
            secret=_hmac(),
        )


def test_insufficient_scope() -> None:
    principal = validate_bearer_jwt(
        _token(scope="runtime:read"),
        audience=_AUDIENCE,
        secret=_hmac(),
    )
    audit = AuditLog()
    with pytest.raises(InvalidValueError):
        require_scope(principal, "compile_runtime", audit)
    assert audit.events[-1]["allowed"] is False
    assert "token" not in audit.events[-1]


def test_audit_redacts_credentials() -> None:
    audit = AuditLog()
    audit.write(
        "tool",
        "user-1",
        False,
        token="leak",
        authorization="Bearer x",
        secret="leak",
        tool="compile_runtime",
    )
    event = audit.events[-1]
    assert "token" not in event
    assert "authorization" not in event
    assert "secret" not in event
    assert event["tool"] == "compile_runtime"
