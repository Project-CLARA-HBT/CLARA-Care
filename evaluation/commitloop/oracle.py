"""Deterministic synthetic protocol oracle; no model or clinician labels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    normalized = [_event(item) for item in visible]
    satisfied = evaluate_predicate(case.fulfillment_predicate, normalized)
    conflicts = [
        item["evidence_id"] for item in normalized if item["relation"] == "contradicts"
    ]
    target_pair = (
        (case.target.get("system"), case.target.get("code"))
        if isinstance(case.target, dict)
        else (None, None)
    )
    target_statuses = {
        item.status
        for item in visible
        if target_pair in item.codes and item.resource_type == "Observation"
    }
    if "replaced" in target_statuses:
        lifecycle_state = "SUPERSEDED"
    elif "revoked" in target_statuses:
        lifecycle_state = "CANCELLED"
    elif "preliminary" in target_statuses:
        lifecycle_state = "PARTIALLY_SATISFIED"
    else:
        lifecycle_state = "SATISFIED" if satisfied else "OPEN"
    if conflicts:
        evidence_state = "CONFLICTED"
    elif normalized:
        evidence_state = "CLEAR"
    else:
        evidence_state = "INSUFFICIENT_EVIDENCE"
    if case.due_time is None:
        timeliness = "UNKNOWN"
    elif valid_cutoff < case.due_time:
        timeliness = "BEFORE_DUE"
    else:
        timeliness = "OVERDUE"
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
