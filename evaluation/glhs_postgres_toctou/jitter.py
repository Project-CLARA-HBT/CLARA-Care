"""Deterministic pre-barrier jitter and interleaving-mode primitives.

The GLHS-CONCURRENCY-REPETITION-V1 study perturbs barrier arrivals with a
deterministic jitter offset drawn from the frozen seed list
(``repeat_manifest``). The jitter is applied *before* a party reaches the
barrier rendezvous (``pre_barrier``), which shifts arrival order and therefore
the realized interleaving across repetitions.

Properties:

- ``jitter_offset_ns(seed, party_index, range_ns)`` is a pure, deterministic
  function of its arguments: the same (seed, party_index, range) always yields
  the same offset. This makes the set of applied delays reproducible.
- ``JitteredBarrier`` wraps any ``BarrierLike`` and applies a deterministic
  per-party delay before delegating to the wrapped barrier. Party index is
  assigned by arrival order; which real thread takes which index is a property
  of the operating-system scheduler, and every realized phase is recorded so no
  order is ever assumed.
- ``interleaving_mode_for_repetition`` maps a seed to one of the frozen modes
  (``a_first`` / ``b_first`` / ``randomized``) deterministically.

This module never opens a database connection and holds no global mutable
state beyond each barrier instance.
"""

from __future__ import annotations

import hashlib
import random
import threading
import time
from collections.abc import Sequence

from evaluation.glhs_postgres_toctou.barrier import PhaseRecord
from evaluation.glhs_postgres_toctou.schedule_primitives import BarrierLike

JITTER_MODE_A_FIRST = "a_first"
JITTER_MODE_B_FIRST = "b_first"
JITTER_MODE_RANDOMIZED = "randomized"
JITTER_MODES = (JITTER_MODE_A_FIRST, JITTER_MODE_B_FIRST, JITTER_MODE_RANDOMIZED)


def jitter_offset_ns(seed: int, party_index: int, range_ns: int) -> int:
    """Deterministic jitter offset in ``[-range_ns, +range_ns]``.

    Pure function: identical inputs always produce identical output. The offset
    is uniform over the integer span implied by ``range_ns``.
    """
    if range_ns < 0:
        raise ValueError("jitter_range_ns_must_be_non_negative")
    derived = int.from_bytes(
        hashlib.sha256(f"{seed}:{party_index}:{range_ns}".encode()).digest()[:8],
        "big",
    )
    rng = random.Random(derived)
    return rng.randint(-range_ns, range_ns)


def interleaving_mode_for_repetition(seed: int, modes: Sequence[str] = JITTER_MODES) -> str:
    """Deterministically pick the frozen interleaving mode for a repetition seed."""
    allowed = tuple(modes)
    if not allowed:
        raise ValueError("interleaving_modes_empty")
    for mode in allowed:
        if mode not in JITTER_MODES:
            raise ValueError(f"unknown_interleaving_mode:{mode}")
    return allowed[(seed % len(allowed))]


class JitteredBarrier:
    """``BarrierLike`` wrapper that applies deterministic pre-barrier jitter.

    Each ``wait`` call sleeps a deterministic delay derived from the frozen seed
    and the party's arrival index, then delegates to the wrapped barrier. Phase
    records (including the post-jitter release timestamps) are preserved from
    the wrapped barrier.
    """

    def __init__(
        self,
        inner: BarrierLike,
        *,
        seed: int,
        range_ns: int,
        parties: int,
        mode: str = JITTER_MODE_RANDOMIZED,
        timeout_s: float = 30.0,
    ) -> None:
        if mode not in JITTER_MODES:
            raise ValueError(f"unknown_interleaving_mode:{mode}")
        self._inner = inner
        self._seed = seed
        self._range_ns = range_ns
        self._parties = parties
        self._mode = mode
        self._timeout_s = timeout_s
        self._lock = threading.Lock()
        self._arrivals = 0
        self._jitter_records: list[dict[str, int | str]] = []

    @property
    def parties(self) -> int:
        return self._parties

    @property
    def broken(self) -> bool:
        return self._inner.broken

    @property
    def phase_records(self) -> tuple[PhaseRecord, ...]:
        return self._inner.phase_records

    @property
    def jitter_records(self) -> tuple[dict[str, int | str], ...]:
        with self._lock:
            return tuple(dict(record) for record in self._jitter_records)

    def _delay_for(self, party_index: int) -> int:
        if self._mode == JITTER_MODE_A_FIRST:
            return 0 if party_index == 0 else 2 * self._range_ns
        if self._mode == JITTER_MODE_B_FIRST:
            return 2 * self._range_ns if party_index == 0 else 0
        return jitter_offset_ns(self._seed, party_index, self._range_ns) + self._range_ns

    def wait(self, phase: str = "release") -> int:
        with self._lock:
            party_index = self._arrivals % self._parties
            self._arrivals += 1
        offset_ns = jitter_offset_ns(self._seed, party_index, self._range_ns)
        delay_ns = self._delay_for(party_index)
        with self._lock:
            self._jitter_records.append(
                {
                    "phase": phase,
                    "party_index": party_index,
                    "offset_ns": offset_ns,
                    "applied_delay_ns": delay_ns,
                }
            )
        if delay_ns:
            time.sleep(delay_ns / 1_000_000_000.0)
        return self._inner.wait(phase)

    def reset(self) -> None:
        with self._lock:
            self._arrivals = 0
            self._jitter_records.clear()
        self._inner.reset()
