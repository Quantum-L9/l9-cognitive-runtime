"""Bounded in-memory MCP run result store with TTL and LRU eviction.

Isolation guarantees: collision-resistant run IDs, per-principal ownership,
TTL + maximum-entry bounds, and thread-safe access. Retrieval is
anti-enumerating — unknown, expired, and cross-principal lookups all raise the
same typed ``RunNotFoundError``. The principal is a caller-supplied string until
hosted OAuth binds it to the token subject (MCP-011C); this is a pre-auth
limitation, documented and not relied upon for isolation on the hosted path.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from l9_cognitive_runtime.models.errors import ModelValidationError


class RunNotFoundError(ModelValidationError):
    """Typed not-found for unknown, expired, or cross-principal runs."""


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    principal: str
    created_at: float
    expires_at: float
    payload: dict[str, Any]
    resource_uri: str


@dataclass
class InMemoryRunStore:
    """Thread-safe bounded store. No cross-run leakage; collision-resistant IDs."""

    max_entries: int = 128
    ttl_seconds: float = 3600.0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _items: dict[str, RunRecord] = field(default_factory=dict, repr=False)
    _order: list[str] = field(default_factory=list, repr=False)

    def create(self, principal: str, payload: dict[str, Any]) -> RunRecord:
        now = time.time()
        run_id = secrets.token_urlsafe(16)
        record = RunRecord(
            run_id=run_id,
            principal=principal,
            created_at=now,
            expires_at=now + self.ttl_seconds,
            payload=dict(payload),
            resource_uri=f"l9://runs/{run_id}",
        )
        with self._lock:
            self._evict_locked(now)
            self._items[run_id] = record
            self._order.append(run_id)
            while len(self._order) > self.max_entries:
                old = self._order.pop(0)
                self._items.pop(old, None)
        return record

    def get(self, run_id: str, principal: str) -> RunRecord | None:
        with self._lock:
            self._evict_locked(time.time())
            record = self._items.get(run_id)
            if record is None or record.principal != principal:
                return None
            # LRU touch
            self._order.remove(run_id)
            self._order.append(run_id)
            return record

    def require(self, run_id: str, principal: str) -> RunRecord:
        """Return a run or raise ``RunNotFoundError`` (anti-enumerating)."""
        record = self.get(run_id, principal)
        if record is None:
            raise RunNotFoundError("run not found", path=run_id)
        return record

    def list_for_principal(self, principal: str) -> list[RunRecord]:
        with self._lock:
            self._evict_locked(time.time())
            return [self._items[i] for i in self._order if self._items[i].principal == principal]

    def _evict_locked(self, now: float) -> None:
        expired = [rid for rid, rec in self._items.items() if rec.expires_at <= now]
        for rid in expired:
            self._items.pop(rid, None)
            if rid in self._order:
                self._order.remove(rid)
