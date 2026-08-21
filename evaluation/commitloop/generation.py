"""Typed model-assisted construction with deterministic source-bound acceptance."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clara_api.glhs.predicate_dsl import validate_predicate

from evaluation.commitloop.note_generation import render_anchor_note
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REVIEWER_MODEL,
    EvaluationClient,
    ProviderResult,
    parse_json_object_content,
)
from evaluation.commitloop.schema import ConstructedCase, TimelineEvent

REVIEW_SCHEMA = {
    "name": "commitloop_nonclinical_review_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["faithful", "executable", "future_leakage", "issues"],
        "properties": {
            "faithful": {"type": "boolean"},
            "executable": {"type": "boolean"},
            "future_leakage": {"type": "boolean"},
            "issues": {"type": "array", "maxItems": 16, "items": {"type": "string"}},
        },
    },
    "strict": True,
}

_PROMPTS = {
    "construction_review": (
        "commitloop-review-deterministic-construction.v3",
        "review_system.txt",
    ),
    "note_review": ("commitloop-review-deterministic-note.v3", "review_system.txt"),
}
REQUESTS_PER_ACCEPTED_CASE = len(_PROMPTS)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _prompt_text(stage: str) -> str:
    stage_id, filename = _PROMPTS[stage]
    template = (Path(__file__).parent / "prompts" / filename).read_text(encoding="utf-8").strip()
    return f"{stage_id}\n{template}"


def _prompt_hash(stage: str) -> str:
    return hashlib.sha256(_prompt_text(stage).encode()).hexdigest()


def _record(stage: str, result: ProviderResult) -> dict[str, object]:
    return {
        "stage": stage,
        "prompt_sha256": _prompt_hash(stage),
        "requested_model_id": result.requested_model_id,
        "reported_model_id": result.reported_model_id,
        "request_sha256": result.request_sha256,
        "response_sha256": result.response_sha256,
        "usage": result.usage,
        "latency_ms": result.latency_ms,
        "attempts": result.attempts,
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def _call(
    client: EvaluationClient,
    *,
    model: str,
    stage: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, object]]:
    result = client.complete(
        model=model,
        messages=[
            {"role": "system", "content": _prompt_text(stage)},
            {"role": "user", "content": _canonical(payload)},
        ],
        response_schema=schema,
        max_tokens=1024,
    )
    parsed = parse_json_object_content(result.content)
    if not isinstance(parsed, dict):
        raise TypeError("generation_output_not_object")
    return parsed, _record(stage, result)


def _expected_candidate(case: ConstructedCase) -> dict[str, object]:
    return {
        "anchor_evidence_id": case.anchor_evidence_id,
        "action": case.action,
        "target": case.target,
        "due_time": case.due_time.isoformat() if case.due_time else None,
    }


def _review_event(event: TimelineEvent) -> dict[str, object]:
    return {
        "evidence_id": event.evidence_id,
        "resource_type": event.resource_type,
        "status": event.status,
        "codes": [list(item) for item in event.codes],
        "valid_at": event.valid_at.isoformat() if event.valid_at else None,
        "known_at": event.known_at.isoformat(),
        "relation": event.source.get("relation"),
    }


def _validate_review(review: dict[str, Any], *, note_stage: bool = False) -> None:
    required = {"faithful", "executable", "future_leakage", "issues"}
    if set(review) != required:
        raise ValueError("review_schema_invalid")
    if (
        review["faithful"] is not True
        or review["future_leakage"] is not False
        or not isinstance(review["issues"], list)
        or review["issues"]
    ):
        raise ValueError("model_assisted_item_rejected")
    if note_stage:
        if not isinstance(review["executable"], bool):
            raise ValueError("review_schema_invalid")
    elif review["executable"] is not True:
        raise ValueError("model_assisted_item_rejected")


def construct_with_model_review(
    *,
    case: ConstructedCase,
    events: tuple[TimelineEvent, ...],
    generator: EvaluationClient,
    reviewer: EvaluationClient,
) -> dict[str, Any]:
    """Review deterministic construction; models never author clinical projections."""

    if case.status != "ELIGIBLE" or case.fulfillment_predicate is None:
        return {
            "case_id": case.case_id,
            "status": "NO_ELIGIBLE_CASE",
            "reason": case.reason,
            "clinical_adjudication": "NOT_RUN",
            "stages": [],
        }
    anchor_events = tuple(item for item in events if item.evidence_id == case.anchor_evidence_id)
    if len(anchor_events) != 1:
        raise ValueError("candidate_anchor_not_in_source")
    candidate = _expected_candidate(case)
    predicate = validate_predicate(case.fulfillment_predicate)
    deterministic_note = render_anchor_note(case)
    source_packet = {
        "case_id": case.case_id,
        "anchor": candidate,
        "source_scope": "anchor_event_only",
        "source_event_ids": [anchor_events[0].evidence_id],
        "source_events": [_review_event(anchor_events[0])],
        "instruction": "review_only_do_not_rewrite_source_owned_projection",
    }
    stages = []
    construction_review, record = _call(
        generator,
        model=GENERATOR_MODEL,
        stage="construction_review",
        payload={
            "source": source_packet,
            "deterministic_candidate": candidate,
            "deterministic_predicate": predicate,
            "frozen_projection_rule": {
                "action": "complete_service_request",
                "fulfillment_resource_type": "Observation",
                "fulfillment_status": "final",
                "target_system_and_code": "copy_exactly_from_anchor",
            },
        },
        schema=REVIEW_SCHEMA,
    )
    stages.append(record)
    _validate_review(construction_review)
    note_review, record = _call(
        reviewer,
        model=REVIEWER_MODEL,
        stage="note_review",
        payload={
            "source": source_packet,
            "deterministic_candidate": candidate,
            "deterministic_note": deterministic_note,
            "frozen_projection_rule": "serialize_anchor_fields_only",
        },
        schema=REVIEW_SCHEMA,
    )
    stages.append(record)
    _validate_review(note_review, note_stage=True)
    return {
        "case_id": case.case_id,
        "status": "ACCEPTED",
        "candidate": candidate,
        "predicate": predicate,
        "synthetic_note": deterministic_note,
        "validator_decision": "DETERMINISTIC_ACCEPT",
        "construction_mode": "deterministic_projection_with_dual_model_review",
        "evidence_class": "synthetic_source_grounded",
        "clinical_adjudication": "NOT_RUN",
        "stages": stages,
    }
