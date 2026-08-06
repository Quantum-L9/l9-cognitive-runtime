"""GitHub org/team numeric-ID trust mapping (optional L9CR-MCP-015)."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from l9_cognitive_runtime.mcp.auth import AuditLog
from l9_cognitive_runtime.models.errors import InvalidValueError


@dataclass(frozen=True)
class TrustPolicy:
    """Immutable numeric org/team policy — names never authorize."""

    org_id: int
    team_ids: frozenset[int]
    cache_ttl_seconds: float = 30.0
    negative_ttl_seconds: float = 10.0


@dataclass(frozen=True)
class Membership:
    user_id: int
    org_id: int
    team_ids: frozenset[int]
    active: bool


class MembershipSource(Protocol):
    def fetch(self, user_id: int, org_id: int) -> Membership: ...


@dataclass
class _CacheEntry:
    allowed: bool
    expires_at: float
    membership: Membership | None = None


@dataclass
class GitHubTrustResolver:
    """Fail-closed membership resolver with ± cache and single-flight refresh."""

    policy: TrustPolicy
    source: MembershipSource
    audit: AuditLog = field(default_factory=AuditLog)
    _cache: dict[int, _CacheEntry] = field(default_factory=dict)
    _locks: dict[int, threading.Lock] = field(default_factory=dict)
    _global: threading.Lock = field(default_factory=threading.Lock)
    now: Callable[[], float] = time.time

    def _lock_for(self, user_id: int) -> threading.Lock:
        with self._global:
            return self._locks.setdefault(user_id, threading.Lock())

    def decide(self, user_id: int) -> bool:
        now = self.now()
        cached = self._cache.get(user_id)
        if cached and cached.expires_at > now:
            self.audit.write(
                "trust",
                str(user_id),
                cached.allowed,
                source="cache",
                org_id=self.policy.org_id,
            )
            return cached.allowed

        with self._lock_for(user_id):
            cached = self._cache.get(user_id)
            if cached and cached.expires_at > self.now():
                self.audit.write(
                    "trust",
                    str(user_id),
                    cached.allowed,
                    source="cache",
                    org_id=self.policy.org_id,
                )
                return cached.allowed
            try:
                membership = self.source.fetch(user_id, self.policy.org_id)
            except Exception as exc:  # fail closed on GitHub/transport errors
                self.audit.write(
                    "trust",
                    str(user_id),
                    False,
                    source="error",
                    reason=type(exc).__name__,
                )
                self._cache[user_id] = _CacheEntry(
                    allowed=False,
                    expires_at=self.now() + self.policy.negative_ttl_seconds,
                )
                return False

            allowed = self._evaluate(membership)
            ttl = (
                self.policy.cache_ttl_seconds
                if allowed
                else self.policy.negative_ttl_seconds
            )
            self._cache[user_id] = _CacheEntry(
                allowed=allowed,
                expires_at=self.now() + ttl,
                membership=membership,
            )
            self.audit.write(
                "trust",
                str(user_id),
                allowed,
                source="refresh",
                org_id=self.policy.org_id,
                team_ids=sorted(membership.team_ids),
            )
            return allowed

    def _evaluate(self, membership: Membership) -> bool:
        if not membership.active:
            return False
        if membership.org_id != self.policy.org_id:
            return False
        return bool(membership.team_ids & self.policy.team_ids)

    def revoke(self, user_id: int, *, reason: str) -> None:
        self._cache[user_id] = _CacheEntry(
            allowed=False,
            expires_at=self.now() + self.policy.negative_ttl_seconds,
        )
        self.audit.write("trust", str(user_id), False, source="revoke", reason=reason)


def reject_github_pat_as_mcp_bearer(token: str) -> None:
    """GitHub PATs/App tokens must never be accepted as MCP bearer credentials."""
    lowered = token.strip().lower()
    prefixes = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")
    if any(lowered.startswith(p) for p in prefixes):
        raise InvalidValueError(
            "github token cannot be used as MCP bearer",
            path="authorization",
        )


def verify_webhook_signature(body: bytes, signature_header: str, secret: str) -> None:
    """Validate GitHub webhook HMAC (sha256=…)."""
    if not signature_header.startswith("sha256="):
        raise InvalidValueError("invalid webhook signature", path="x-hub-signature-256")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    if not hmac.compare_digest(expected, signature_header):
        raise InvalidValueError("webhook signature mismatch", path="x-hub-signature-256")


def apply_membership_webhook(
    resolver: GitHubTrustResolver,
    event: dict[str, Any],
) -> None:
    """Revoke on team/org membership removal events (fail closed)."""
    action = str(event.get("action") or "")
    if action not in {"removed", "deleted", "member_removed"}:
        return
    user = event.get("member") or event.get("user") or {}
    user_id = user.get("id")
    if not isinstance(user_id, int):
        raise InvalidValueError("webhook missing numeric user id", path="member.id")
    resolver.revoke(user_id, reason=f"webhook:{action}")
