"""Pure LifeMap truth and task state machines."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidTransition(ValueError):
    pass


TRUTH_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"user_reported", "confirmed", "invalidated", "entered_in_error"}),
    "user_reported": frozenset({"confirmed", "disputed", "superseded", "invalidated"}),
    "confirmed": frozenset({"disputed", "superseded", "invalidated"}),
    "disputed": frozenset({"confirmed", "superseded", "invalidated"}),
    "superseded": frozenset(),
    "invalidated": frozenset(),
    "entered_in_error": frozenset(),
}

LEGACY_TRUTH_STATES = {
    "extracted_draft": "draft",
    "reported": "user_reported",
}

TASK_TRANSITIONS: dict[str, dict[str, str]] = {
    "proposed": {"accept": "accepted", "reject": "rejected", "cancel": "cancelled"},
    "accepted": {"start": "in_progress", "complete": "completed", "cancel": "cancelled"},
    "in_progress": {"complete": "completed", "cancel": "cancelled"},
    "rejected": {},
    "completed": {},
    "cancelled": {},
    "expired": {},
}
TODAY_ELIGIBLE_TASK_STATES = frozenset({"accepted", "in_progress"})


def canonical_truth_state(state: str) -> str:
    return LEGACY_TRUTH_STATES.get(state, state)


def require_truth_transition(current: str, target: str) -> tuple[str, str]:
    source = canonical_truth_state(current)
    destination = canonical_truth_state(target)
    if source not in TRUTH_TRANSITIONS or destination not in TRUTH_TRANSITIONS[source]:
        raise InvalidTransition(f"truth:{source}->{destination}")
    return source, destination


@dataclass(frozen=True)
class TaskTransition:
    action: str
    from_state: str
    to_state: str


def require_task_transition(current: str, action: str) -> TaskTransition:
    destination = TASK_TRANSITIONS.get(current, {}).get(action)
    if destination is None:
        raise InvalidTransition(f"task:{current}:{action}")
    return TaskTransition(action=action, from_state=current, to_state=destination)


def task_is_today_eligible(state: str) -> bool:
    return state.strip().lower().replace("-", "_") in TODAY_ELIGIBLE_TASK_STATES
