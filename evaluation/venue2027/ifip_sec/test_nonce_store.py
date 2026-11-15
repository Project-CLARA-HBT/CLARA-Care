"""Tests for IFIP_SEC-X03_nonce_store — consume-once nonce store.

Positive controls: first consume CONSUMED, second consume REPLAY_DETECTED,
expired nonce EXPIRED, sweep reclaims memory (size returns to 0), validation
fails closed with stable reason codes, and the manifest contract
``consume(nonce, tenant, tx) -> ConsumeOutcome`` shape is honoured via
``consume(nonce, expires_at, now) -> ConsumeResult`` (first-class outcomes,
never exceptions miscounted as safe rejections).

Adversarial controls: N threads racing the SAME nonce through real
``threading`` locks admit EXACTLY one CONSUMED (barrier-synchronized, repeated
to flush scheduling luck); the PostgreSQL stub raises
``PostgresBackendUnavailable`` instead of faking durability; and an
equivalence control proves the pluggable :class:`NonceBackend` Protocol seam
dispatches to a custom backend implementation.

No network, no database, no hidden clock: every ``now``/``expires_at`` is an
explicit integer argument; deterministic by construction.
"""

from __future__ import annotations

import threading

import pytest

from evaluation.venue2027.ifip_sec.nonce_store import (
    CONSUMED,
    EXPIRED,
    NONCE_MIN_LENGTH,
    NONCE_STORE_VERSION,
    RC_BACKEND_UNAVAILABLE,
    RC_EXPIRES_AT_BAD_TYPE,
    RC_NONCE_MISSING,
    RC_NONCE_TOO_SHORT,
    RC_NOW_BAD_TYPE,
    REPLAY_DETECTED,
    ConsumeResult,
    InMemoryNonceBackend,
    NonceBackend,
    NonceBackendError,
    NonceStore,
    NonceStoreError,
    PostgresBackendUnavailable,
    PostgresNonceBackend,
)

_VALID_NONCE = "nonce-0001-abcdefgh123456"  # >= 16 chars (receipt v1 syntax)
_NOW = 1_700_000_000
_EXPIRES_AT = _NOW + 3600


def _store(**kwargs: object) -> NonceStore:
    return NonceStore(sweep_interval=None, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Positive — first consume, replay, expiry, sweep
# ---------------------------------------------------------------------------


def test_version_and_first_consume_ok() -> None:
    store = _store()
    assert NONCE_STORE_VERSION == "1.0.0"
    result = store.consume(_VALID_NONCE, _EXPIRES_AT, _NOW)
    assert isinstance(result, ConsumeResult)
    assert result.outcome == CONSUMED
    assert result.detail == CONSUMED
    assert result.nonce == _VALID_NONCE
    assert result.consumed is True


def test_second_consume_is_replay_detected() -> None:
    store = _store()
    assert store.consume(_VALID_NONCE, _EXPIRES_AT, _NOW).outcome == CONSUMED
    replay = store.consume(_VALID_NONCE, _EXPIRES_AT, _NOW + 1)
    assert replay.outcome == REPLAY_DETECTED
    assert replay.consumed is False


def test_expired_nonce_is_expired() -> None:
    store = _store()
    result = store.consume(_VALID_NONCE, _EXPIRES_AT, _EXPIRES_AT)
    # Half-open window [issue, expires_at): consumption at exactly expiry fails
    # closed as EXPIRED (matching receipt schema "expiry strictly after issued").
    assert result.outcome == EXPIRED


def test_expired_record_never_re_admits_later_nonce() -> None:
    store = _store()
    assert store.consume(_VALID_NONCE, _NOW + 10, _NOW).outcome == CONSUMED
    # Presenting the same nonce after expiry must never re-admit.
    assert store.consume(_VALID_NONCE, _NOW + 10, _NOW + 11).outcome == EXPIRED
    # Distinct nonce inside window still admits (independent records).
    other = "nonce-0002-zyxwvu9876543210"
    assert store.consume(other, _EXPIRES_AT, _NOW).outcome == CONSUMED


def test_sweep_reclaims_memory() -> None:
    backend = InMemoryNonceBackend()
    store = _store(backend=backend)
    for i in range(5):
        store.consume(f"nonce-sweep-{i:012d}", _NOW + 10, _NOW)
    assert backend.size() == 5
    assert len(backend) == 5
    reclaimed = store.sweep(now=_NOW + 11)
    assert reclaimed == 5
    assert backend.size() == 0
    # Sweeping again with nothing expired is a no-op.
    assert store.sweep(now=_NOW + 12) == 0


def test_sweep_keeps_live_records_and_respects_limit() -> None:
    backend = InMemoryNonceBackend()
    store = _store(backend=backend)
    store.consume("nonce-live-000000000001", _NOW + 100, _NOW)
    store.consume("nonce-dead-00000000002", _NOW + 10, _NOW)
    assert store.sweep(now=_NOW + 11, limit=10) == 1
    assert backend.size() == 1
    assert backend.lookup("nonce-live-000000000001") == _NOW + 100


def test_auto_sweep_bounds_memory_every_interval() -> None:
    backend = InMemoryNonceBackend()
    store = NonceStore(backend, sweep_interval=8)
    for i in range(16):
        # Record i claims at now=_NOW+i with window closing at _NOW+5+i, so it
        # is live at consume time (memory grows) but expires 5 ticks later.
        store.consume(f"nonce-auto-{i:014d}", _NOW + 5 + i, _NOW + i)
    # Two auto-sweeps fired (after the 8th and 16th consume) at
    # now=_NOW+7 and now=_NOW+15: they reclaimed records 0-2 and 3-10
    # (11 total). Without auto-sweep all 16 records would remain.
    assert backend.size() == 5


def test_validation_fails_closed_with_stable_reason_codes() -> None:
    store = _store()
    with pytest.raises(NonceStoreError) as missing:
        store.consume("", _EXPIRES_AT, _NOW)  # type: ignore[arg-type]
    assert missing.value.args[0] == RC_NONCE_MISSING
    with pytest.raises(NonceStoreError) as short:
        store.consume("short", _EXPIRES_AT, _NOW)
    assert short.value.args[0] == RC_NONCE_TOO_SHORT
    assert NONCE_MIN_LENGTH == 16
    with pytest.raises(NonceStoreError) as bad_exp:
        store.consume(_VALID_NONCE, "soon", _NOW)  # type: ignore[arg-type]
    assert bad_exp.value.args[0] == RC_EXPIRES_AT_BAD_TYPE
    with pytest.raises(NonceStoreError) as bad_now:
        store.consume(_VALID_NONCE, _EXPIRES_AT, 1.5)  # type: ignore[arg-type]
    assert bad_now.value.args[0] == RC_NOW_BAD_TYPE
    with pytest.raises(NonceStoreError) as bad_bool:
        store.consume(_VALID_NONCE, True, _NOW)  # type: ignore[arg-type]
    assert bad_bool.value.args[0] == RC_EXPIRES_AT_BAD_TYPE


def test_store_rejects_bad_sweep_interval() -> None:
    with pytest.raises(NonceStoreError):
        NonceStore(sweep_interval=0)
    with pytest.raises(NonceStoreError):
        NonceStore(sweep_interval=True)


# ---------------------------------------------------------------------------
# Adversarial — concurrent same-nonce race, postgres stub, backend seam
# ---------------------------------------------------------------------------


def _race_same_nonce(threads: int, store: NonceStore) -> list[ConsumeResult]:
    barrier = threading.Barrier(threads)
    results: list[ConsumeResult | None] = [None] * threads
    start_lock = threading.Lock()

    def worker(idx: int) -> None:
        with start_lock:
            pass  # ensure all worker closures created before first start
        barrier.wait()
        results[idx] = store.consume(_VALID_NONCE, _EXPIRES_AT, _NOW)

    workers = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    return [r for r in results if r is not None]


@pytest.mark.parametrize("threads", [2, 4, 8, 16])
def test_concurrent_same_nonce_admits_exactly_one(threads: int) -> None:
    for _ in range(5):  # repeat to flush scheduling luck
        store = _store()
        results = _race_same_nonce(threads, store)
        assert len(results) == threads
        consumed = [r for r in results if r.outcome == CONSUMED]
        replayed = [r for r in results if r.outcome == REPLAY_DETECTED]
        assert len(consumed) == 1, f"expected exactly 1 CONSUMED, got {len(consumed)}"
        assert len(replayed) == threads - 1
        assert store.is_claimed(_VALID_NONCE)


def test_race_mixes_live_and_expired_windows_fail_closed() -> None:
    # Concurrent consumers presenting the SAME nonce with conflicting expiry
    # windows: exactly one claim wins; every loser is classified by the
    # recorded window (fails closed — never CONSUMED twice).
    threads = 8
    store = _store()
    barrier = threading.Barrier(threads)
    results: list[ConsumeResult | None] = [None] * threads

    def worker(idx: int) -> None:
        expires = _EXPIRES_AT if idx % 2 == 0 else _NOW - 5  # half expired
        barrier.wait()
        results[idx] = store.consume(_VALID_NONCE, expires, _NOW)

    workers = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    consumed = [r for r in results if r is not None and r.outcome == CONSUMED]
    assert len(consumed) == 1


def test_postgres_stub_without_connection_raises_not_fakes() -> None:
    with pytest.raises(PostgresBackendUnavailable) as construction:
        PostgresNonceBackend()
    assert construction.value.reason_code == RC_BACKEND_UNAVAILABLE
    with pytest.raises(PostgresBackendUnavailable):
        PostgresNonceBackend(None)
    # Backend built with a (pretend) connection still refuses to fake SQL ops.
    backend = PostgresNonceBackend(connection=object())
    for operation, call in (
        ("reserve", lambda: backend.reserve(_VALID_NONCE, _EXPIRES_AT)),
        ("lookup", lambda: backend.lookup(_VALID_NONCE)),
        ("release", lambda: backend.release(_VALID_NONCE)),
        ("expired", lambda: list(backend.expired(_NOW, 10))),
        ("size", backend.size),
    ):
        with pytest.raises(PostgresBackendUnavailable) as raised:
            call()
        assert raised.value.reason_code == RC_BACKEND_UNAVAILABLE
        assert operation in raised.value.detail


def test_postgres_stub_is_nonce_backend_error() -> None:
    # The stub's failure surfaces through the documented exception hierarchy so
    # callers can catch NonceBackendError without importing the concrete class.
    assert issubclass(PostgresBackendUnavailable, NonceBackendError)
    assert issubclass(NonceBackendError, NonceStoreError)


def test_custom_backend_via_protocol_seam() -> None:
    # The store depends only on the NonceBackend Protocol: a hand-rolled
    # backend (e.g. the future real PostgreSQL one) plugs in unmodified.
    class RecordingBackend:
        def __init__(self) -> None:
            self.reserved: list[str] = []
            self.records: dict[str, int] = {}

        def reserve(self, nonce: str, expires_at: int) -> bool:
            if nonce in self.records:
                return False
            self.records[nonce] = expires_at
            self.reserved.append(nonce)
            return True

        def lookup(self, nonce: str) -> int | None:
            return self.records.get(nonce)

        def release(self, nonce: str) -> None:
            self.records.pop(nonce, None)

        def expired(self, now: int, limit: int) -> list[str]:
            found = [n for n, exp in self.records.items() if exp <= now]
            return found[:limit]

        def size(self) -> int:
            return len(self.records)

    backend = RecordingBackend()
    assert isinstance(backend, NonceBackend)  # runtime_checkable Protocol
    store = _store(backend=backend)  # type: ignore[arg-type]
    assert store.consume(_VALID_NONCE, _EXPIRES_AT, _NOW).outcome == CONSUMED
    assert store.consume(_VALID_NONCE, _EXPIRES_AT, _NOW).outcome == REPLAY_DETECTED
    assert backend.reserved == [_VALID_NONCE]
