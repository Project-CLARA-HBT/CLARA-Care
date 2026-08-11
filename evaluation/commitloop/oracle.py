"""Deterministic synthetic protocol oracle; no model or clinician labels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from clara_api.glhs.commitments import policy_for
from clara_api.glhs.predicate_dsl import evaluate_predicate

from evaluation.commitloop.schema import ConstructedCase, TimelineEvent


def _event(item: TimelineEvent) -> dict[str, Any]:
    first_code = item.codes[0] if item.codes else (None, None)
    return {
        "evidence_id": item.evidence_id,
        "resource_type": item.resource_type,
        "system": first_code[0],
        "code": first_code[1],
        "status": item.status,
        "valid_at": item.valid_at.isoformat() if item.valid_at else None,
        "known_at": item.known_at.isoformat(),
        "relation": item.source.get("relation"),
    }


def grace_end_for_case(case: ConstructedCase) -> datetime | None:
    """Resolve the same domain-default grace window used by the runtime policy."""

    if case.due_time is None or case.domain is None:
        return None
    return case.due_time + policy_for(case.domain).default_grace


def _first_satisfied_at(
    predicate: dict[str, Any], events: list[dict[str, Any]]
) -> datetime | None:
    prefix: list[dict[str, Any]] = []
    for event in events:
        prefix.append(event)
        if evaluate_predicate(predicate, prefix):
            value = event.get("valid_at")
            return datetime.fromisoformat(value) if isinstance(value, str) else None
    return None


def _timeliness(
    case: ConstructedCase, *, cutoff: datetime, decisive_at: datetime | None
) -> str:
    """Mirror production reconciliation: compare completion time, else cutoff."""

    if case.due_time is None:
        return "NOT_APPLICABLE"
    point = decisive_at or cutoff
    if point < case.due_time:
        return "BEFORE_DUE"
    grace_end = grace_end_for_case(case)
    if grace_end is not None and point <= grace_end:
        return "IN_GRACE"
    return "OVERDUE"


def compile_construction_gold(
    case: ConstructedCase,
    events: tuple[TimelineEvent, ...],
    *,
    valid_cutoff: datetime,
    known_cutoff: datetime,
) -> dict[str, Any]:
    if case.status != "ELIGIBLE" or case.fulfillment_predicate is None:
        return {
            "case_id": case.case_id,
            "status": "NO_ELIGIBLE_CASE",
            "evidence_class": "synthetic_protocol_oracle",
            "clinical_adjudication": "NOT_RUN",
        }
    visible = [
        item
        for item in events
        if item.valid_at is not None
        and item.valid_at <= valid_cutoff
        and item.known_at <= known_cutoff
    ]
    normalized = sorted(
        (_event(item) for item in visible),
        key=lambda item: (str(item["valid_at"]), str(item["evidence_id"])),
    )
    fulfillment_at = _first_satisfied_at(case.fulfillment_predicate, normalized)
    conflicts = [
        item["evidence_id"] for item in normalized if item["relation"] == "contradicts"
    ]
    target_pair = (
        (case.target.get("system"), case.target.get("code"))
        if isinstance(case.target, dict)
        else (None, None)
    )
    target_events = [
        item
        for item in visible
        if target_pair in item.codes and item.resource_type == "Observation"
    ]

    def first_status_at(status: str) -> datetime | None:
        values = sorted(
            item.valid_at
            for item in target_events
            if item.status == status and item.valid_at is not None
        )
        return values[0] if values else None

    cancellation_at = first_status_at("revoked")
    supersession_at = first_status_at("replaced")
    partial_at = first_status_at("preliminary")
    if cancellation_at is not None:
        lifecycle_state = "CANCELLED"
        decisive_at = cancellation_at
    elif supersession_at is not None:
        lifecycle_state = "SUPERSEDED"
        decisive_at = supersession_at
    elif fulfillment_at is not None:
        lifecycle_state = "SATISFIED"
        decisive_at = fulfillment_at
    elif partial_at is not None:
        lifecycle_state = "PARTIALLY_SATISFIED"
        decisive_at = partial_at
    else:
        lifecycle_state = "OPEN"
        decisive_at = None
    if conflicts:
        evidence_state = "CONFLICTED"
    elif normalized:
        evidence_state = "CLEAR"
    else:
        evidence_state = "INSUFFICIENT_EVIDENCE"
    timeliness = _timeliness(case, cutoff=valid_cutoff, decisive_at=decisive_at)
    escalation = (
        "ESCALATE"
        if evidence_state in {"CONFLICTED", "INSUFFICIENT_EVIDENCE"}
        or lifecycle_state == "OPEN" and timeliness == "OVERDUE"
        else "NO_ESCALATION"
    )
    return {
        "case_id": case.case_id,
        "status": "SCORABLE",
        "lifecycle_state": lifecycle_state,
        "evidence_state": evidence_state,
        "timeliness_state": timeliness,
        "escalation_state": escalation,
        "visible_evidence_ids": [item.evidence_id for item in visible],
        "conflict_evidence_ids": conflicts,
        "evidence_class": "synthetic_protocol_oracle",
        "clinical_adjudication": "NOT_RUN",
    }
