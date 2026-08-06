"""Isolation and eviction tests for RunStore."""

from __future__ import annotations

import time

from l9_cognitive_runtime.mcp.run_store import InMemoryRunStore


def test_collision_resistant_ids() -> None:
    store = InMemoryRunStore()
    ids = {store.create("p", {"n": i}).run_id for i in range(50)}
    assert len(ids) == 50


def test_cross_principal_isolation() -> None:
    store = InMemoryRunStore()
    rec = store.create("alice", {"x": 1})
    assert store.get(rec.run_id, "alice") is not None
    assert store.get(rec.run_id, "bob") is None


def test_ttl_eviction() -> None:
    store = InMemoryRunStore(ttl_seconds=0.05)
    rec = store.create("p", {"x": 1})
    time.sleep(0.06)
    assert store.get(rec.run_id, "p") is None


def test_lru_capacity() -> None:
    store = InMemoryRunStore(max_entries=3, ttl_seconds=60)
    a = store.create("p", {"n": 1})
    store.create("p", {"n": 2})
    store.create("p", {"n": 3})
    store.create("p", {"n": 4})
    assert store.get(a.run_id, "p") is None
