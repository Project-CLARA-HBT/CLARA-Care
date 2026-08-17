from __future__ import annotations

from evaluation.governance_adversarial.cache_observer import (
    CACHE_OBSERVATION_FIELDS,
    CacheObservation,
    ImmutableSnapshotStore,
    ReadOnlyCacheStore,
    measure,
    require_fields,
)


class _DeleteHostileStore:
    """Read-only-looking store that fails loudly if anything tries to delete."""

    def __init__(self, snapshot: dict[str, bytes]) -> None:
        self._snapshot = dict(snapshot)

    def exists(self, key: str) -> bool:
        return key in self._snapshot

    def get_bytes(self, key: str) -> bytes | None:
        return self._snapshot.get(key)

    def get_ttl(self, key: str) -> int | None:
        return None

    def delete(self, *keys: str) -> None:
        raise AssertionError("observer must never delete cache entries")


def test_read_only_store_protocol_exposes_no_delete_method() -> None:
    delete_methods = {name for name in dir(ReadOnlyCacheStore) if "delete" in name.lower()}
    assert not delete_methods
    assert hasattr(ReadOnlyCacheStore, "exists")
    assert hasattr(ReadOnlyCacheStore, "get_bytes")
    assert hasattr(ReadOnlyCacheStore, "get_ttl")


def test_immutable_snapshot_store_has_no_mutation_surface() -> None:
    store = ImmutableSnapshotStore({"k": b"v"})
    assert not hasattr(store, "delete")
    assert not hasattr(store, "set")
    assert not hasattr(store, "set_bytes")
    assert store.exists("k")
    assert store.get_bytes("k") == b"v"
    assert store.get_ttl("missing") is None


def test_measure_never_deletes_even_on_hostile_store() -> None:
    store = _DeleteHostileStore({"cache:key": b"opaque"})
    before_reads = 0
    observation = measure(
        store=store,
        cache_key="cache:key",
        revoked_at_monotonic=100.0,
        stale_served=True,
        governance_reevaluated=False,
        invalid_persistent_commit=False,
        now_monotonic=100.5,
    )
    assert observation.stale_cache_entry_exists
    assert observation.stale_cache_returned
    assert observation.revocation_to_not_visible_latency == 500.0
    assert before_reads == 0


def test_measure_derives_w2_fields_correctly() -> None:
    store = ImmutableSnapshotStore({"cache:key": b"opaque"}, ttl={"cache:key": 120})
    observation = measure(
        store=store,
        cache_key="cache:key",
        revoked_at_monotonic=1_000.0,
        stale_served=True,
        governance_reevaluated=False,
        invalid_persistent_commit=True,
        now_monotonic=1_002.0,
    )
    assert observation == CacheObservation(
        stale_cache_entry_exists=True,
        stale_cache_returned=True,
        governance_reevaluation_occurred=False,
        stale_cache_caused_invalid_persistent_commit=True,
        revocation_to_not_visible_latency=2_000.0,
    )
    assert store.read_count == 1


def test_measure_latency_zero_when_stale_entry_never_visible() -> None:
    store = ImmutableSnapshotStore({})
    observation = measure(
        store=store,
        cache_key="cache:key",
        revoked_at_monotonic=1_000.0,
        stale_served=False,
        governance_reevaluated=True,
        invalid_persistent_commit=False,
        now_monotonic=1_002.0,
    )
    assert observation.stale_cache_entry_exists is False
    assert observation.stale_cache_returned is False
    assert observation.revocation_to_not_visible_latency == 0.0


def test_absent_observation_is_neutral() -> None:
    observation = CacheObservation.absent()
    assert observation == CacheObservation(False, False, False, False, 0.0)
    assert not any(observation.asdict().values())


def test_observation_exposes_every_w2_field() -> None:
    observation = CacheObservation(False, False, False, False, 0.0)
    assert set(observation.asdict()) == set(CACHE_OBSERVATION_FIELDS)
    require_fields(observation)


def test_require_fields_accepts_complete_observation() -> None:
    from dataclasses import replace

    drifted = replace(CacheObservation.absent(), stale_cache_entry_exists=True)
    require_fields(drifted)  # every field is present, so no error
