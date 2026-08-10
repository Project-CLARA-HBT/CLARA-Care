"""Deterministic source-grounded commitment candidates from supported FHIR resources."""

from __future__ import annotations

import hashlib
from datetime import datetime

from evaluation.commitloop.schema import ConstructedCase, TimelineEvent


def _due_time(event: TimelineEvent) -> datetime | None:
    for field in ("occurrencePeriod", "scheduledPeriod"):
        period = event.source.get(field)
        if isinstance(period, dict) and isinstance(period.get("end"), str):
            from evaluation.commitloop.fhir_ingest import _parse_time

            return _parse_time(period["end"])
    scheduled = event.source.get("scheduledDateTime")
    if isinstance(scheduled, str):
        from evaluation.commitloop.fhir_ingest import _parse_time

        return _parse_time(scheduled)
    return None


def mine_candidates(
    subject_token: str, events: tuple[TimelineEvent, ...]
) -> tuple[ConstructedCase, ...]:
    cases = []
    for event in events:
        if event.resource_type not in {"ServiceRequest", "ProcedureRequest"} or event.status not in {
            "active",
            "draft",
            "on-hold",
        }:
            continue
        if event.valid_at is None or not event.codes:
            continue
        system, code = event.codes[0]
        due = _due_time(event)
        case_id = hashlib.sha256(f"{subject_token}:{event.evidence_id}".encode()).hexdigest()[:24]
        cases.append(
            ConstructedCase(
                case_id=case_id,
                subject_token=subject_token,
                status="ELIGIBLE",
                reason=None,
                anchor_evidence_id=event.evidence_id,
                domain="observations",
                action="complete_service_request",
                target={"system": system, "code": code},
                anchor_valid_time=event.valid_at,
                anchor_known_time=event.known_at,
                due_time=due,
                fulfillment_predicate={
                    "op": "event",
                    "equals": {
                        "resource_type": "Observation",
                        "system": system,
                        "code": code,
                        "status": "final",
                    },
                },
            )
        )
    if cases:
        return tuple(cases)
    return (
        ConstructedCase(
            case_id=hashlib.sha256(f"{subject_token}:no-eligible".encode()).hexdigest()[:24],
            subject_token=subject_token,
            status="NO_ELIGIBLE_CASE",
            reason="no_source_grounded_future_oriented_resource",
            anchor_evidence_id=None,
            domain=None,
            action=None,
            target=None,
            anchor_valid_time=None,
            anchor_known_time=None,
            due_time=None,
            fulfillment_predicate=None,
        ),
    )
