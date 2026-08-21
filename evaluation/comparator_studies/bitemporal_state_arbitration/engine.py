"""A small, non-GLHS bi-temporal arbitration mechanism.

This module deliberately has no imports from CLARA.  It is suitable only for
the mechanism-level comparison documented in BTSA_IMPLEMENTATION_NOTES.md;
it is not represented as a reproduction of unavailable Zhao implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArbitrationEvent:
    event_id: str
    slot: str
    value: str
    valid_from: datetime
    valid_to: datetime | None
    known_at: datetime
    authority: int
    relation: str = "SUPPORT"
    target_id: str | None = None


@dataclass(frozen=True)
class ArbitrationResult:
    active_ids: tuple[str, ...]
    superseded_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    historical_ids: tuple[str, ...]


def _overlaps(left: ArbitrationEvent, right: ArbitrationEvent) -> bool:
    return not (
        left.valid_to is not None
        and left.valid_to < right.valid_from
        or right.valid_to is not None
        and right.valid_to < left.valid_from
    )


def arbitrate(
    events: list[ArbitrationEvent], *, valid_at: datetime, known_at: datetime
) -> ArbitrationResult:
    """Arbitrate a single slot at bitemporal cut-offs without deleting history.

    Operators are explicit inputs: SUPPORT retains evidence, REFINE replaces a
    targeted active assertion, SUPERSEDE retires its target, and
    BRANCH-CONFLICT retains comparable contradictory active branches.
    """
    visible = sorted(
        (
            item
            for item in events
            if item.known_at <= known_at
            and item.valid_from <= valid_at
            and (item.valid_to is None or item.valid_to >= valid_at)
        ),
        key=lambda item: (item.known_at, item.event_id),
    )
    active: dict[str, ArbitrationEvent] = {}
    superseded: set[str] = set()
    conflicts: set[str] = set()
    historical = {item.event_id for item in events if item.known_at <= known_at}
    for event in visible:
        if event.relation not in {"SUPPORT", "REFINE", "SUPERSEDE", "BRANCH-CONFLICT"}:
            raise ValueError("unsupported_relation")
        if event.relation in {"REFINE", "SUPERSEDE"}:
            if not event.target_id or event.target_id not in active:
                raise ValueError("missing_active_target")
            superseded.add(event.target_id)
            active.pop(event.target_id)
        if event.relation == "SUPPORT" and event.target_id is not None:
            if event.target_id not in active:
                raise ValueError("missing_active_target")
            continue
        if event.relation == "BRANCH-CONFLICT":
            if not event.target_id or event.target_id not in active:
                raise ValueError("missing_active_target")
            conflicts.update((event.event_id, event.target_id))
        for other in active.values():
            if (
                other.slot == event.slot
                and other.value != event.value
                and other.authority == event.authority
                and _overlaps(other, event)
            ):
                conflicts.update((other.event_id, event.event_id))
        active[event.event_id] = event
    return ArbitrationResult(
        active_ids=tuple(sorted(active)),
        superseded_ids=tuple(sorted(superseded)),
        conflict_ids=tuple(sorted(conflicts)),
        historical_ids=tuple(sorted(historical)),
    )
