"""Isolation, eviction, and typed-not-found tests for the MCP run store."""

from __future__ import annotations

import concurrent.futures
import time

import pytest

from l9_cognitive_runtime.mcp.run_store import InMemoryRunStore, RunNotFoundError


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


def test_lru_capacity_bound() -> None:
    store = InMemoryRunStore(max_entries=3, ttl_seconds=60)
    a = store.create("p", {"n": 1})
    store.create("p", {"n": 2})
    store.create("p", {"n": 3})
    store.create("p", {"n": 4})
    assert store.get(a.run_id, "p") is None
    assert len(store.list_for_principal("p")) == 3


def test_require_raises_typed_not_found_for_unknown() -> None:
    store = InMemoryRunStore()
    with pytest.raises(RunNotFoundError):
        store.require("does-not-exist", "p")


def test_require_anti_enumeration_cross_principal() -> None:
    # Cross-principal lookup raises the SAME error as unknown — no enumeration.
    store = InMemoryRunStore()
    rec = store.create("alice", {"x": 1})
    with pytest.raises(RunNotFoundError):
        store.require(rec.run_id, "bob")


def test_require_raises_for_expired() -> None:
    store = InMemoryRunStore(ttl_seconds=0.05)
    rec = store.create("p", {"x": 1})
    time.sleep(0.06)
    with pytest.raises(RunNotFoundError):
        store.require(rec.run_id, "p")


def test_concurrent_creates_do_not_overwrite() -> None:
    store = InMemoryRunStore(max_entries=1000)

    def _create(idx: int) -> str:
        return store.create("p", {"n": idx}).run_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_create, range(200)))
    # All IDs unique (no collision/overwrite) and all independently retrievable.
    assert len(set(ids)) == 200
    assert all(store.get(rid, "p") is not None for rid in ids)


def test_payload_is_copied_not_aliased() -> None:
    store = InMemoryRunStore()
    payload = {"digests": {"graph": "abc"}}
    rec = store.create("p", payload)
    payload["digests"] = {"graph": "TAMPERED"}  # mutate caller's copy
    stored = store.get(rec.run_id, "p")
    assert stored is not None
    assert stored.payload["digests"]["graph"] == "abc"


def test_one_principal_cannot_evict_another_principals_run() -> None:
    """RG-010a: capacity pressure evicts from the principal holding the most
    runs, so a burst from one principal leaves another's run retrievable."""
    store = InMemoryRunStore(max_entries=4, ttl_seconds=60)
    alice = store.create("alice", {"n": 0})
    mallory = [store.create("mallory", {"n": i}) for i in range(store.max_entries)]
    assert store.require(alice.run_id, "alice") == alice
    # The global bound is unchanged: mallory's oldest run made room.
    assert store.get(mallory[0].run_id, "mallory") is None
    assert len(store.list_for_principal("alice")) + len(store.list_for_principal("mallory")) == 4
    assert [r.run_id for r in store.list_for_principal("mallory")] == [
        r.run_id for r in mallory[1:]
    ]


def test_single_principal_eviction_is_oldest_first_and_bounded() -> None:
    """RG-010b (preserved): one principal over capacity loses its least
    recently used runs and the store never exceeds ``max_entries``."""
    store = InMemoryRunStore(max_entries=3, ttl_seconds=60)
    first = store.create("p", {"n": 1})
    second = store.create("p", {"n": 2})
    store.create("p", {"n": 3})
    assert store.get(first.run_id, "p") is not None  # LRU touch
    store.create("p", {"n": 4})
    assert store.get(second.run_id, "p") is None
    assert store.get(first.run_id, "p") is not None
    store.create("p", {"n": 5})
    assert len(store.list_for_principal("p")) == 3
