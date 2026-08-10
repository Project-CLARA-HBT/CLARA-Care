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
)
from evaluation.commitloop.schema import ConstructedCase, TimelineEvent

CANDIDATE_SCHEMA = {
    "name": "commitloop_candidate_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["anchor_evidence_id", "action", "target", "due_time"],
        "properties": {
            "anchor_evidence_id": {"type": "string"},
            "action": {"type": "string"},
            "target": {
                "type": "object",
                "additionalProperties": False,
                "required": ["system", "code"],
                "properties": {"system": {"type": "string"}, "code": {"type": "string"}},
            },
            "due_time": {"type": ["string", "null"]},
        },
    },
    "strict": True,
}

PREDICATE_SCHEMA = {
    "name": "commitloop_predicate_proposal_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["predicate"],
        "properties": {"predicate": {"type": "object"}},
    },
    "strict": True,
}

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

NOTE_SCHEMA = {
    "name": "commitloop_anchor_note_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["note"],
        "properties": {"note": {"type": "string", "maxLength": 4000}},
    },
    "strict": True,
}

_PROMPTS = {
    "candidate": ("commitloop-generation-candidate.v1", "generation_candidate_system.txt"),
    "predicate": ("commitloop-generation-predicate.v1", "generation_predicate_system.txt"),
    "candidate_review": ("commitloop-review-candidate.v1", "review_system.txt"),
    "note": ("commitloop-generation-anchor-note.v1", "generation_note_system.txt"),
    "note_review": ("commitloop-review-anchor-note.v1", "review_system.txt"),
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
    parsed = json.loads(result.content)
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
    """Run construction stages; deterministic code remains the acceptance authority."""

    if case.status != "ELIGIBLE" or case.fulfillment_predicate is None:
        return {
            "case_id": case.case_id,
            "status": "NO_ELIGIBLE_CASE",
            "reason": case.reason,
            "clinical_adjudication": "NOT_RUN",
            "stages": [],
        }
    event_ids = {item.evidence_id for item in events}
    if case.anchor_evidence_id not in event_ids:
        raise ValueError("candidate_anchor_not_in_source")
    source_packet = {
        "case_id": case.case_id,
        "anchor": _expected_candidate(case),
        "source_event_ids": sorted(event_ids),
        "instruction": "repeat_only_source_grounded_fields",
    }
    stages = []
    candidate, record = _call(
        generator,
        model=GENERATOR_MODEL,
        stage="candidate",
        payload=source_packet,
        schema=CANDIDATE_SCHEMA,
    )
    stages.append(record)
    if candidate != _expected_candidate(case):
        raise ValueError("generated_candidate_not_source_grounded")
    predicate_output, record = _call(
        generator,
        model=GENERATOR_MODEL,
        stage="predicate",
        payload={"candidate": candidate, "allowed_source_event_ids": sorted(event_ids)},
        schema=PREDICATE_SCHEMA,
    )
    stages.append(record)
    proposed_predicate = validate_predicate(predicate_output.get("predicate"))
    expected_predicate = validate_predicate(case.fulfillment_predicate)
    if proposed_predicate != expected_predicate:
        raise ValueError("generated_predicate_not_source_grounded")
    review, record = _call(
        reviewer,
        model=REVIEWER_MODEL,
        stage="candidate_review",
        payload={"source": source_packet, "candidate": candidate, "predicate": proposed_predicate},
        schema=REVIEW_SCHEMA,
    )
    stages.append(record)
    _validate_review(review)
    deterministic_note = render_anchor_note(case)
    note_output, record = _call(
        generator,
        model=GENERATOR_MODEL,
        stage="note",
        payload={"candidate": candidate, "allowed_note_projection": deterministic_note},
        schema=NOTE_SCHEMA,
    )
    stages.append(record)
    if note_output.get("note") != deterministic_note:
        raise ValueError("generated_note_not_anchor_projection")
    note_review, record = _call(
        reviewer,
        model=REVIEWER_MODEL,
        stage="note_review",
        payload={"candidate": candidate, "note": deterministic_note},
        schema=REVIEW_SCHEMA,
    )
    stages.append(record)
    _validate_review(note_review, note_stage=True)
    return {
        "case_id": case.case_id,
        "status": "ACCEPTED",
        "candidate": candidate,
        "predicate": proposed_predicate,
        "synthetic_note": deterministic_note,
        "validator_decision": "DETERMINISTIC_ACCEPT",
        "evidence_class": "synthetic_source_grounded",
        "clinical_adjudication": "NOT_RUN",
        "stages": stages,
    }
