"""Reusable concurrency primitives for barrier-controlled GLHS v2 schedules.

Contains a phased multi-party barrier, a no-op barrier, a lock-wait-tracing
competing lock, and the lock-order specification that governs their use.

Lock-order specification (see also
``research/glhs_journal/GLHS_CONCURRENCY_V2_DESIGN.md``):

1. Coordination order is fixed: a ``PhasedBarrier`` rendezvous is always
   entered before any ``CompetingLock`` acquisition.
2. A ``CompetingLock`` is held only for the mutation critical section and is
   always released before ``session.commit()``; it is never held across a
   transaction commit.
3. A barrier is never waited on while holding a ``CompetingLock`` or inside a
   transaction that already holds row locks.
4. Writer-side ordering: barrier release -> optional competing lock -> begin ->
   single authoritative governance row mutation -> release lock -> commit.
   No writer ever holds two governance row locks simultaneously.
5. Each schedule owns its own ``TransactionTrace``; trace appends are
   single-threaded per schedule and hold no cross-thread lock.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from threading import BrokenBarrierError

from evaluation.glhs_postgres_toctou.schedule_primitives import (
    TransactionTrace,
    now_monotonic_ns,
)


@dataclass(frozen=True)
class PhaseRecord:
    """A completed barrier phase with its monotonic release timestamp."""

    name: str
    release_ns: int
    parties: int
    arrivals: int


class PhasedBarrier:
    """A reusable multi-party rendezvous with named phases.

    Each participant calls ``wait(phase)``. When the final participant arrives
    the barrier records a monotonic ``release_ns`` and releases everyone. The
    ``phase`` string is a generation marker, so one barrier instance can drive
    several controlled release points. A timeout or a party missing the
    rendezvous breaks the barrier; ``reset`` restores it for reuse.
    """

    def __init__(self, parties: int, *, timeout_s: float = 30.0) -> None:
        if parties < 1:
            raise ValueError("v2_barrier_parties_must_be_positive")
        self._parties = parties
        self._timeout_s = timeout_s
        self._cond = threading.Condition()
        self._arrivals = 0
        self._generation = 0
        self._broken = False
        self._records: list[PhaseRecord] = []

    @property
    def parties(self) -> int:
        return self._parties

    @property
    def broken(self) -> bool:
        with self._cond:
            return self._broken

    @property
    def phase_records(self) -> tuple[PhaseRecord, ...]:
        with self._cond:
            return tuple(self._records)

    def wait(self, phase: str = "release") -> int:
        """Block until all parties arrive; returns the 0-based arrival index."""
        with self._cond:
            if self._broken:
                raise BrokenBarrierError("v2_barrier_broken")
            generation = self._generation
            index = self._arrivals
            self._arrivals += 1
            if self._arrivals == self._parties:
                self._records.append(
                    PhaseRecord(
                        name=phase,
                        release_ns=now_monotonic_ns(),
                        parties=self._parties,
                        arrivals=self._arrivals,
                    )
                )
                self._generation += 1
                self._arrivals = 0
                self._cond.notify_all()
                return index
            deadline = time.monotonic() + self._timeout_s
            while self._generation == generation:
                if self._broken:
                    raise BrokenBarrierError("v2_barrier_broken")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._broken = True
                    self._cond.notify_all()
                    raise BrokenBarrierError("v2_barrier_timeout")
                self._cond.wait(timeout=remaining)
            return index

    def reset(self) -> None:
        """Restore the barrier to a clean state for a fresh generation."""
        with self._cond:
            self._arrivals = 0
            self._generation += 1
            self._broken = False
            self._records.clear()


class NullBarrier:
    """A no-op barrier: ``wait`` returns immediately and never breaks.

    Lets single-threaded schedules exercise a writer without any rendezvous
    while still passing the same ``BarrierLike`` interface.
    """

    @property
    def broken(self) -> bool:
        return False

    @property
    def phase_records(self) -> tuple[PhaseRecord, ...]:
        return ()

    def wait(self, phase: str = "release") -> int:
        return 0

    def reset(self) -> None:
        return None


class CompetingLock:
    """A mutex whose acquisition is recorded as a lock-wait trace.

    Exercises the ``competing_lock`` interleaving coverage: the observer can
    verify that two competing parties actually contended on the same lock and
    record how long the loser waited.
    """

    def __init__(
        self,
        name: str,
        trace: TransactionTrace | None = None,
        *,
        timeout_s: float = 30.0,
    ) -> None:
        self._name = name
        self._trace = trace
        self._lock = threading.Lock()
        self._timeout_s = timeout_s

    def acquire(self) -> bool:
        started = now_monotonic_ns()
        acquired = self._lock.acquire(timeout=self._timeout_s)
        waited_ns = now_monotonic_ns() - started
        if self._trace is not None:
            self._trace.lock_wait(lock=self._name, waited_ns=waited_ns, acquired=acquired)
        return acquired

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *_args: object) -> None:
        self.release()
