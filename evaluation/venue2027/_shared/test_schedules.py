"""Tests for SH-schedule_engine (deterministic logical schedules)."""

from __future__ import annotations

import itertools

import pytest

from evaluation.venue2027._shared.schedules import (
    ScheduleError,
    ScheduleScope,
    dedup_audit,
    generate_schedule,
    schedule_manifest_jsonl,
)


def _scope() -> ScheduleScope:
    return ScheduleScope(
        operations=("op_read", "op_write", "op_commit"),
        barriers=("barrier_lock", "barrier_consume"),
        max_schedules=16,
    )


def test_same_seed_is_byte_identical() -> None:
    a = schedule_manifest_jsonl(7, _scope())
    b = schedule_manifest_jsonl(7, _scope())
    assert a == b
    assert a.strip()


def test_schedule_ids_and_digests_are_unique() -> None:
    schedules = list(generate_schedule(7, _scope()))
    assert len(schedules) == len({s.schedule_id for s in schedules})
    assert len(schedules) == len({s.logical_schedule_digest for s in schedules})


def test_dedup_audit_reports_zero_duplicates() -> None:
    result = dedup_audit(7, _scope())
    assert result["ok"] is True
    assert result["duplicates"] == 0


def test_two_seeds_give_different_orderings() -> None:
    first = [s.logical_schedule_digest for s in generate_schedule(1, _scope())]
    second = [s.logical_schedule_digest for s in generate_schedule(2, _scope())]
    assert first != second


def test_logical_clock_is_strictly_monotonic() -> None:
    for schedule in generate_schedule(3, _scope()):
        clocks = [e.logical_clock for e in schedule.events]
        assert clocks == sorted(clocks)
        assert len(set(clocks)) == len(clocks)


def test_all_operations_appear_exactly_once() -> None:
    scope = _scope()
    for schedule in generate_schedule(3, scope):
        seen = [e.operation for e in schedule.events]
        assert sorted(seen) == sorted(scope.operations)


def test_max_schedules_is_respected_and_bounded_by_permutations() -> None:
    scope = ScheduleScope(operations=("a", "b"), max_schedules=100)
    total = len(list(itertools.permutations(scope.operations)))
    assert len(list(generate_schedule(5, scope))) == total


def test_backward_clock_is_refused() -> None:
    from evaluation.venue2027._shared.schedules import ScheduleEvent, _assert_monotonic

    events = (
        ScheduleEvent("e0", "a", 2, None),
        ScheduleEvent("e1", "b", 1, None),
    )
    with pytest.raises(ScheduleError) as exc:
        _assert_monotonic(events)
    assert exc.value.reason_code == "BACKWARD_CLOCK"


def test_empty_scope_refused() -> None:
    with pytest.raises(ScheduleError) as exc:
        list(generate_schedule(1, ScheduleScope(operations=())))
    assert exc.value.reason_code == "EMPTY_SCOPE"


def test_duplicate_operations_refused() -> None:
    with pytest.raises(ScheduleError) as exc:
        list(generate_schedule(1, ScheduleScope(operations=("a", "a"))))
    assert exc.value.reason_code == "DUPLICATE_OPERATION"
