"""Deterministic bitemporal reconciliation for Clinical Commitments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from clara_api.db.models import GlhsClinicalCommitmentVersion
from clara_api.glhs.predicate_dsl import evaluate_predicate

_AUTHORITY_RANK = {
    "unverified": 0,
    "patient_report": 1,
    "device_measurement": 2,
    "clinician_order": 3,
    "lab_verified": 3,
    "pharmacist_verified": 4,
    "clinician_confirmed": 4,
    "clinician_diagnosis": 4,
}


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


@dataclass(frozen=True)
class CommitmentProductState:
    lifecycle_state: str
    evidence_state: str
    timeliness_state: str
    matched_evidence_ids: tuple[str, ...]
    excluded_evidence: tuple[dict[str, str], ...]
    reason_codes: tuple[str, ...]


def _visible_events(
    events: list[dict[str, Any]], *, valid_at: datetime, known_at: datetime
) -> tuple[list[dict[str, Any]], tuple[dict[str, str], ...]]:
    visible = []
    excluded = []
    for event in events:
        event_valid = _time(event.get("valid_at"))
        event_known = _time(event.get("known_at"))
        identifier = str(event.get("evidence_id", "unknown"))
        if event_valid is None or event_known is None:
            excluded.append({"evidence_id": identifier, "reason": "missing_bitemporal_time"})
        elif event_valid > valid_at:
            excluded.append({"evidence_id": identifier, "reason": "future_valid_time"})
        elif event_known > known_at:
            excluded.append({"evidence_id": identifier, "reason": "not_yet_known"})
        else:
            visible.append(event)
    visible.sort(key=lambda item: (_time(item["valid_at"]), str(item.get("evidence_id", ""))))
    return visible, tuple(excluded)


def _first_satisfied_at(
    predicate: dict[str, Any] | None, events: list[dict[str, Any]]
) -> datetime | None:
    if predicate is None:
        return None
    prefix: list[dict[str, Any]] = []
    for event in events:
        prefix.append(event)
        if evaluate_predicate(predicate, prefix):
            return _time(event["valid_at"])
    return None


def _timeliness(
    version: GlhsClinicalCommitmentVersion,
    *,
    cutoff: datetime,
    satisfied_at: datetime | None,
) -> str:
    if version.due_time is None:
        return "NOT_APPLICABLE"
    point = satisfied_at or cutoff
    due = version.due_time
    grace = version.grace_end
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    if grace is not None and grace.tzinfo is None:
        grace = grace.replace(tzinfo=UTC)
    if point < due:
        return "BEFORE_DUE"
    if grace is not None and point <= grace:
        return "IN_GRACE"
    return "OVERDUE"


def _comparable_contradictions(
    events: list[dict[str, Any]], *, authority_class: str
) -> list[dict[str, Any]]:
    threshold = _AUTHORITY_RANK.get(authority_class, 0)
    return [
        item
        for item in events
        if item.get("relation") == "contradicts"
        and (
            not isinstance(item.get("authority"), str)
            or _AUTHORITY_RANK.get(item["authority"], 0) >= threshold
        )
    ]


def evaluate_commitment(
    version: GlhsClinicalCommitmentVersion,
    events: list[dict[str, Any]],
    *,
    valid_at: datetime,
    known_at: datetime,
) -> CommitmentProductState:
    """Evaluate a frozen version without mutating canonical state."""

    visible, excluded = _visible_events(events, valid_at=valid_at, known_at=known_at)
    earliest = version.earliest_valid_time
    if earliest is not None and earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=UTC)
    eligible = []
    for item in visible:
        event_time = _time(item.get("valid_at"))
        if earliest is None or (event_time is not None and event_time >= earliest):
            eligible.append(item)
    trigger = getattr(version, "conditional_trigger_json", None)
    triggered = trigger is None or evaluate_predicate(trigger, eligible)
    cancellation_at = _first_satisfied_at(version.cancellation_predicate_json, eligible)
    supersession_at = _first_satisfied_at(
        getattr(version, "supersession_predicate_json", None), eligible
    )
    fulfillment_at = _first_satisfied_at(version.fulfillment_predicate_json, eligible)
    partial_at = _first_satisfied_at(version.partial_predicate_json, eligible)
    contradictions = _comparable_contradictions(
        visible, authority_class=version.authority_class
    )
    if contradictions:
        evidence_state = "CONFLICTED"
    elif not visible:
        evidence_state = "INSUFFICIENT_EVIDENCE"
    else:
        evidence_state = "CLEAR"
    if not triggered:
        lifecycle = "OPEN"
        decisive_at = None
        reason = "conditional_trigger_not_satisfied"
    elif cancellation_at is not None:
        lifecycle = "CANCELLED"
        decisive_at = cancellation_at
        reason = "cancellation_predicate_satisfied"
    elif supersession_at is not None:
        lifecycle = "SUPERSEDED"
        decisive_at = supersession_at
        reason = "supersession_predicate_satisfied"
    elif fulfillment_at is not None:
        lifecycle = "SATISFIED"
        decisive_at = fulfillment_at
        reason = "fulfillment_predicate_satisfied"
    elif partial_at is not None:
        lifecycle = "PARTIALLY_SATISFIED"
        decisive_at = partial_at
        reason = "partial_predicate_satisfied"
    else:
        lifecycle = "OPEN"
        decisive_at = None
        reason = "no_terminal_predicate_satisfied"
    matched = tuple(
        str(item["evidence_id"])
        for item in visible
        if isinstance(item.get("evidence_id"), str)
    )
    reasons = [reason]
    if contradictions:
        reasons.append("comparable_evidence_conflict")
    if not visible:
        reasons.append("no_visible_evidence")
    return CommitmentProductState(
        lifecycle_state=lifecycle,
        evidence_state=evidence_state,
        timeliness_state=_timeliness(version, cutoff=valid_at, satisfied_at=decisive_at),
        matched_evidence_ids=matched,
        excluded_evidence=excluded,
        reason_codes=tuple(reasons),
    )
