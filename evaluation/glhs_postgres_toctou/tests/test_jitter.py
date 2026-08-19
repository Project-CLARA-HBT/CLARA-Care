"""Tests for deterministic pre-barrier jitter primitives.

No database is connected.
"""

from __future__ import annotations

import pytest

from evaluation.glhs_postgres_toctou.barrier import NullBarrier
from evaluation.glhs_postgres_toctou.jitter import (
    JITTER_MODE_A_FIRST,
    JITTER_MODE_B_FIRST,
    JITTER_MODE_RANDOMIZED,
    JitteredBarrier,
    interleaving_mode_for_repetition,
    jitter_offset_ns,
)
from evaluation.glhs_postgres_toctou.repeat_manifest import build_repeat_manifest


def test_jitter_offset_is_deterministic() -> None:
    assert jitter_offset_ns(7, 3, 200_000_000) == jitter_offset_ns(7, 3, 200_000_000)


def test_jitter_offset_within_range() -> None:
    manifest = build_repeat_manifest()
    range_ns = int(manifest["jitter"]["range_ns"])
    for seed in manifest["jitter"]["seeds"]:
        for party_index in range(4):
            offset = jitter_offset_ns(seed, party_index, range_ns)
            assert -range_ns <= offset <= range_ns


def test_jitter_offset_differs_across_seeds() -> None:
    offsets = {jitter_offset_ns(seed, 0, 200_000_000) for seed in range(20)}
    assert len(offsets) > 1


def test_jitter_range_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="jitter_range_ns_must_be_non_negative"):
        jitter_offset_ns(1, 0, -1)


def test_interleaving_mode_for_repetition_is_deterministic() -> None:
    assert interleaving_mode_for_repetition(123) == interleaving_mode_for_repetition(123)
    modes = {interleaving_mode_for_repetition(seed) for seed in range(12)}
    assert modes == {JITTER_MODE_A_FIRST, JITTER_MODE_B_FIRST, JITTER_MODE_RANDOMIZED}


def test_interleaving_mode_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown_interleaving_mode"):
        interleaving_mode_for_repetition(1, modes=("a_first", "bogus"))


def test_interleaving_mode_rejects_empty() -> None:
    with pytest.raises(ValueError, match="interleaving_modes_empty"):
        interleaving_mode_for_repetition(1, modes=())


def test_jittered_barrier_records_phases_through_inner() -> None:
    inner = NullBarrier()
    barrier = JitteredBarrier(inner, seed=42, range_ns=1_000_000, parties=2)
    assert barrier.wait("release") == 0
    assert barrier.wait("release") == 0
    assert barrier.parties == 2
    assert barrier.broken is False
    assert len(barrier.jitter_records) == 2
    assert all("offset_ns" in record for record in barrier.jitter_records)


def test_negative_offset_is_realized_as_relative_pre_barrier_delay() -> None:
    inner = NullBarrier()
    barrier = JitteredBarrier(
        inner,
        seed=7,
        range_ns=1_000_000,
        parties=2,
        mode=JITTER_MODE_RANDOMIZED,
    )
    barrier.wait("release")
    record = barrier.jitter_records[0]
    assert -1_000_000 <= record["offset_ns"] <= 1_000_000
    assert 0 <= record["applied_delay_ns"] <= 2_000_000
