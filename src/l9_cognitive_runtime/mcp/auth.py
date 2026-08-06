"""OAuth resource-server helpers and redacted audit middleware (L9CR-MCP-011)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import jwt

from l9_cognitive_runtime.models.errors import InvalidValueError

PROTECTED_RESOURCE_METADATA = {
    "resource": "https://runtime.example/v1/mcp",
    "authorization_servers": ["https://auth.example"],
    "scopes_supported": [
        "runtime:compile",
        "runtime:read",
        "runtime:capabilities",
        "runtime:render",
    ],
}


@dataclass
class Principal:
    subject: str
    scopes: frozenset[str]
    audience: str


@dataclass
class AuditLog:
    events: list[dict[str, Any]] = field(default_factory=list)

    def write(self, action: str, principal: str, allowed: bool, **extra: Any) -> None:
        redacted = {k: v for k, v in extra.items() if k not in {"token", "authorization", "secret"}}
        self.events.append(
            {
                "ts": time.time(),
                "action": action,
                "principal": principal,
                "allowed": allowed,
                **redacted,
            }
        )


SCOPE_BY_TOOL = {
    "runtime_capabilities": "runtime:capabilities",
    "compile_runtime": "runtime:compile",
    "get_bundle_digests": "runtime:read",
    "list_pack_manifest": "runtime:read",
    "validate_pack_path": "runtime:read",
    "get_run": "runtime:read",
    "runtime_render": "runtime:render",
}


def validate_bearer_jwt(
    token: str,
    *,
    audience: str,
    secret: str,
    now: float | None = None,
) -> Principal:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            options={"require": ["exp", "sub", "aud", "scope"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidValueError(
            "jwt validation failed", path="authorization", details=str(exc)
        ) from exc
    exp = float(payload["exp"])
    if exp <= (now or time.time()):
        raise InvalidValueError("token expired", path="exp")
    scopes = frozenset(str(payload["scope"]).split())
    return Principal(subject=str(payload["sub"]), scopes=scopes, audience=str(payload["aud"]))


def require_scope(principal: Principal, tool_name: str, audit: AuditLog) -> None:
    needed = SCOPE_BY_TOOL.get(tool_name)
    if needed is None:
        audit.write("tool", principal.subject, False, tool=tool_name, reason="unknown_tool")
        raise InvalidValueError("unknown tool", path=tool_name)
    allowed = needed in principal.scopes
    audit.write("tool", principal.subject, allowed, tool=tool_name, scope=needed)
    if not allowed:
        raise InvalidValueError("insufficient_scope", path=tool_name, details={"required": needed})
