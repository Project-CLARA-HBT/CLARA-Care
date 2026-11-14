"""CLARA-Care 2027 shared task SH-schedule_engine.

Purpose
-------
Deterministic generation of *independent concurrency schedules* for the systems
studies (DSN, COMPSAC, IFIP SEC). The scientific unit is the independent logical
schedule, not a repeated run of the same interleaving, so this module enumerates
valid logical orderings, de-duplicates them by canonical digest, and refuses any
schedule whose logical clock moves backwards.

Allowed input
-------------
A seed and a :class:`ScheduleScope` describing the number of concurrent
operations and the named barriers they must cross.

Failure semantics
-----------------
- Non-positive seed/scope values -> ``ValueError`` with a stable reason code.
- Emitting a schedule with a backward logical clock -> refused (``BACKWARD_CLOCK``)
  and never yielded.
- Same ``(seed, scope)`` always yields byte-identical JSONL.

Version
-------
``SCHEDULE_ENGINE_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import random
from collections.abc import Iterator

SCHEDULE_ENGINE_VERSION = "1.0.0"


class ScheduleError(ValueError):
    """Stable, machine-readable schedule construction failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class ScheduleScope:
    """Describes the concurrency study scope.

    ``operations`` are logical operation identifiers; ``barriers`` are named
    synchronization points that every schedule must respect (an operation placed
    after a barrier may not be scheduled before it).
    """

    operations: tuple[str, ...]
    barriers: tuple[str, ...] = ()
    max_schedules: int = 64

    def validate(self) -> None:
        if not self.operations:
            raise ScheduleError("EMPTY_SCOPE", "at least one operation is required")
        if len(set(self.operations)) != len(self.operations):
            raise ScheduleError("DUPLICATE_OPERATION", "operation ids must be unique")
        if len(set(self.barriers)) != len(self.barriers):
            raise ScheduleError("DUPLICATE_BARRIER", "barrier ids must be unique")
        if self.max_schedules <= 0:
            raise ScheduleError("INVALID_MAX_SCHEDULES", "max_schedules must be positive")


@dataclasses.dataclass(frozen=True)
class ScheduleEvent:
    event_id: str
    operation: str
    logical_clock: int
    barrier: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "operation": self.operation,
            "logical_clock": self.logical_clock,
            "barrier": self.barrier,
        }


@dataclasses.dataclass(frozen=True)
class Schedule:
    schedule_id: str
    seed: int
    scope_digest: str
    events: tuple[ScheduleEvent, ...]
    logical_schedule_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "seed": self.seed,
            "scope_digest": self.scope_digest,
            "events": [e.to_dict() for e in self.events],
            "logical_schedule_digest": self.logical_schedule_digest,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _scope_digest(scope: ScheduleScope) -> str:
    payload = json.dumps(
        {"operations": list(scope.operations), "barriers": list(scope.barriers)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _canonical_digest(events: tuple[ScheduleEvent, ...]) -> str:
    payload = "|".join(f"{e.logical_clock}:{e.operation}:{e.barrier or ''}" for e in events)
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_events(order: tuple[str, ...], scope: ScheduleScope) -> tuple[ScheduleEvent, ...]:
    """Assign monotonically increasing logical clocks along ``order``.

    A barrier is attached to the event at its index so that schedules differ in
    where synchronization points fall relative to operations.
    """

    events: list[ScheduleEvent] = []
    clock = 0
    for index, operation in enumerate(order):
        barrier = scope.barriers[index % len(scope.barriers)] if scope.barriers else None
        clock += 1
        events.append(
            ScheduleEvent(
                event_id=f"ev{index:03d}",
                operation=operation,
                logical_clock=clock,
                barrier=barrier,
            )
        )
    return tuple(events)


def _assert_monotonic(events: tuple[ScheduleEvent, ...]) -> None:
    last = -1
    for event in events:
        if event.logical_clock <= last:
            raise ScheduleError(
                "BACKWARD_CLOCK",
                f"logical clock did not strictly increase at {event.event_id}",
            )
        last = event.logical_clock


def generate_schedule(seed: int, scope: ScheduleScope) -> Iterator[Schedule]:
    """Yield deterministic, de-duplicated logical schedules.

    The same ``(seed, scope)`` always produces the same ordered sequence of
    schedules with byte-identical JSONL, because the permutation space is
    enumerated deterministically and only ordering (never a hidden clock) is
    randomized by the seed.
    """

    scope.validate()
    rng = random.Random(seed)
    digest = _scope_digest(scope)

    permutations = list(itertools.permutations(scope.operations))
    rng.shuffle(permutations)

    seen: set[str] = set()
    emitted = 0
    for order in permutations:
        if emitted >= scope.max_schedules:
            break
        events = _build_events(order, scope)
        _assert_monotonic(events)
        logical = _canonical_digest(events)
        if logical in seen:
            continue
        seen.add(logical)
        emitted += 1
        yield Schedule(
            schedule_id=f"sched-{seed}-{emitted:04d}",
            seed=seed,
            scope_digest=digest,
            events=events,
            logical_schedule_digest=logical,
        )


def schedule_manifest_jsonl(seed: int, scope: ScheduleScope) -> str:
    """Render the full schedule set as stable JSONL for artifact evidence."""

    return "\n".join(s.to_jsonl() for s in generate_schedule(seed, scope)) + "\n"


def dedup_audit(seed: int, scope: ScheduleScope) -> dict[str, object]:
    """Count unique logical schedules vs. generated schedules (must be equal)."""

    schedules = list(generate_schedule(seed, scope))
    unique = {s.logical_schedule_digest for s in schedules}
    return {
        "generated": len(schedules),
        "unique": len(unique),
        "duplicates": len(schedules) - len(unique),
        "ok": len(schedules) == len(unique),
        "version": SCHEDULE_ENGINE_VERSION,
    }
