from __future__ import annotations

import threading
from threading import BrokenBarrierError

import pytest

from evaluation.glhs_postgres_toctou.barrier import (
    CompetingLock,
    NullBarrier,
    PhasedBarrier,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import TransactionTrace


def test_phased_barrier_releases_all_parties_together() -> None:
    barrier = PhasedBarrier(2, timeout_s=5.0)
    released: list[int] = []

    def participant() -> None:
        released.append(barrier.wait("release"))

    left = threading.Thread(target=participant)
    right = threading.Thread(target=participant)
    left.start()
    right.start()
    left.join(timeout=5)
    right.join(timeout=5)

    assert sorted(released) == [0, 1]
    assert barrier.broken is False
    assert len(barrier.phase_records) == 1
    record = barrier.phase_records[0]
    assert record.name == "release"
    assert record.parties == 2
    assert record.arrivals == 2
    assert record.release_ns > 0


def test_phased_barrier_records_a_fresh_monotonic_release_per_generation() -> None:
    barrier = PhasedBarrier(2, timeout_s=5.0)

    def run_phase(name: str) -> list[int]:
        released: list[int] = []

        def participant() -> None:
            released.append(barrier.wait(name))

        left = threading.Thread(target=participant)
        right = threading.Thread(target=participant)
        left.start()
        right.start()
        left.join(timeout=5)
        right.join(timeout=5)
        return released

    for name in ("mutation", "commit"):
        assert sorted(run_phase(name)) == [0, 1]

    assert [r.name for r in barrier.phase_records] == ["mutation", "commit"]
    assert barrier.phase_records[0].release_ns <= barrier.phase_records[1].release_ns


def test_phased_barrier_timeout_breaks_barrier() -> None:
    barrier = PhasedBarrier(2, timeout_s=0.2)
    with pytest.raises(BrokenBarrierError):
        barrier.wait("release")
    assert barrier.broken is True
    with pytest.raises(BrokenBarrierError):
        barrier.wait("release")


def test_phased_barrier_reset_restores_clean_state() -> None:
    barrier = PhasedBarrier(2, timeout_s=0.2)
    with pytest.raises(BrokenBarrierError):
        barrier.wait("release")
    barrier.reset()
    assert barrier.broken is False
    assert barrier.phase_records == ()
    released: list[int] = []

    def participant() -> None:
        released.append(barrier.wait("release"))

    left = threading.Thread(target=participant)
    right = threading.Thread(target=participant)
    left.start()
    right.start()
    left.join(timeout=5)
    right.join(timeout=5)
    assert sorted(released) == [0, 1]


def test_phased_barrier_refuses_non_positive_parties() -> None:
    with pytest.raises(ValueError, match="v2_barrier_parties_must_be_positive"):
        PhasedBarrier(0)


def test_null_barrier_returns_immediately_and_never_breaks() -> None:
    barrier = NullBarrier()
    assert barrier.wait("release") == 0
    assert barrier.broken is False
    assert barrier.phase_records == ()
    barrier.reset()


def test_competing_lock_is_mutually_exclusive() -> None:
    lock = CompetingLock("profile:1")
    assert lock.acquire() is True
    holder: list[str] = []
    stop = threading.Event()

    def contender() -> None:
        acquired = lock.acquire()
        holder.append("acquired" if acquired else "timed_out")
        stop.set()

    thread = threading.Thread(target=contender)
    thread.start()
    lock.release()
    thread.join(timeout=5)
    assert holder == ["acquired"]


def test_competing_lock_records_lock_wait_trace() -> None:
    trace = TransactionTrace()
    lock = CompetingLock("profile:1", trace=trace)
    lock.acquire()

    thread = threading.Thread(target=lock.acquire)
    thread.start()
    lock.release()
    thread.join(timeout=5)

    assert len(trace.lock_waits) == 2
    assert {w.lock for w in trace.lock_waits} == {"profile:1"}
    assert any(w.acquired is False for w in trace.lock_waits) or any(
        w.waited_ns >= 0 for w in trace.lock_waits
    )
