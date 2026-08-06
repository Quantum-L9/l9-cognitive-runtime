"""OAuth / audit middleware tests."""

from __future__ import annotations

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


def _token(**claims: object) -> str:
    payload = {
        "sub": "user-1",
        "aud": "https://runtime.example/v1/mcp",
        "exp": time.time() + 60,
        "scope": "runtime:compile runtime:read runtime:capabilities",
        **claims,
    }
    return jwt.encode(payload, "secret", algorithm="HS256")


def test_protected_resource_metadata() -> None:
    assert "scopes_supported" in PROTECTED_RESOURCE_METADATA


def test_valid_token_and_scope() -> None:
    principal = validate_bearer_jwt(
        _token(),
        audience="https://runtime.example/v1/mcp",
        secret="secret",
    )
    audit = AuditLog()
    require_scope(principal, "compile_runtime", audit)
    assert audit.events[-1]["allowed"] is True


def test_wrong_audience_rejected() -> None:
    with pytest.raises(InvalidValueError):
        validate_bearer_jwt(
            _token(aud="https://other.example"),
            audience="https://runtime.example/v1/mcp",
            secret="secret",
        )


def test_insufficient_scope() -> None:
    principal = validate_bearer_jwt(
        _token(scope="runtime:read"),
        audience="https://runtime.example/v1/mcp",
        secret="secret",
    )
    audit = AuditLog()
    with pytest.raises(InvalidValueError):
        require_scope(principal, "compile_runtime", audit)
    assert audit.events[-1]["allowed"] is False
    assert "token" not in audit.events[-1]
