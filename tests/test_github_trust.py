"""GitHub-derived trust mapping tests (L9CR-MCP-015)."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import dataclass, field

import pytest

from l9_cognitive_runtime.mcp.github_trust import (
    GitHubTrustResolver,
    Membership,
    TrustPolicy,
    apply_membership_webhook,
    reject_github_pat_as_mcp_bearer,
    verify_webhook_signature,
)
from l9_cognitive_runtime.models.errors import InvalidValueError

POLICY = TrustPolicy(
    org_id=42,
    team_ids=frozenset({7, 9}),
    cache_ttl_seconds=60,
    negative_ttl_seconds=5,
)


@dataclass
class FakeSource:
    members: dict[int, Membership] = field(default_factory=dict)
    fail: bool = False
    calls: int = 0

    def fetch(self, user_id: int, org_id: int) -> Membership:
        self.calls += 1
        if self.fail:
            raise RuntimeError("github down")
        member = self.members.get(user_id)
        if member is None:
            return Membership(user_id=user_id, org_id=org_id, team_ids=frozenset(), active=False)
        return member


def test_numeric_ids_govern_membership() -> None:
    source = FakeSource(
        members={
            100: Membership(100, 42, frozenset({7}), True),
            101: Membership(101, 42, frozenset({99}), True),  # wrong team
            102: Membership(102, 99, frozenset({7}), True),  # wrong org
        }
    )
    resolver = GitHubTrustResolver(POLICY, source)
    assert resolver.decide(100) is True
    assert resolver.decide(101) is False
    assert resolver.decide(102) is False
    assert resolver.decide(103) is False  # unmapped


def test_github_failure_fails_closed() -> None:
    source = FakeSource(fail=True)
    resolver = GitHubTrustResolver(POLICY, source)
    assert resolver.decide(1) is False
    assert resolver.audit.events[-1]["allowed"] is False


def test_positive_cache_and_single_flight() -> None:
    source = FakeSource(members={1: Membership(1, 42, frozenset({7}), True)})
    resolver = GitHubTrustResolver(POLICY, source)
    assert resolver.decide(1) is True
    assert resolver.decide(1) is True
    assert source.calls == 1

    barrier = threading.Barrier(3)
    results: list[bool] = []

    def worker() -> None:
        barrier.wait()
        results.append(resolver.decide(2))

    source.members[2] = Membership(2, 42, frozenset({9}), True)
    source.calls = 0
    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [True, True, True]
    assert source.calls == 1


def test_webhook_revocation() -> None:
    source = FakeSource(members={5: Membership(5, 42, frozenset({7}), True)})
    resolver = GitHubTrustResolver(POLICY, source)
    assert resolver.decide(5) is True
    apply_membership_webhook(resolver, {"action": "removed", "member": {"id": 5}})
    # Cached deny after revoke; source would still say true until refresh.
    assert resolver.decide(5) is False
    assert any(e.get("source") == "revoke" for e in resolver.audit.events)


def test_webhook_signature() -> None:
    body = json.dumps({"action": "removed"}).encode()
    secret = "whsec-" + "x" * 24
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verify_webhook_signature(body, sig, secret)
    with pytest.raises(InvalidValueError):
        verify_webhook_signature(body, "sha256=deadbeef", secret)


def test_github_pat_rejected_as_mcp_bearer() -> None:
    with pytest.raises(InvalidValueError):
        reject_github_pat_as_mcp_bearer("ghp_" + "a" * 40)
    with pytest.raises(InvalidValueError):
        reject_github_pat_as_mcp_bearer("github_pat_" + "b" * 20)
    reject_github_pat_as_mcp_bearer("eyJhbGciOiJIUzI1NiJ9.e30.sig")


def test_inactive_user_denied() -> None:
    source = FakeSource(members={8: Membership(8, 42, frozenset({7}), False)})
    resolver = GitHubTrustResolver(POLICY, source)
    assert resolver.decide(8) is False
