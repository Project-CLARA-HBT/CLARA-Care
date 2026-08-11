from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import synthetic_bundle
from evaluation.commitloop.generation import construct_with_model_review
from evaluation.commitloop.note_generation import render_anchor_note
from evaluation.commitloop.provider import (
    REPORTED_MODEL_ID_BY_REQUESTED,
    EvaluationClient,
    RunLimits,
)


class GenerationFakeTransport:
    def __init__(self, *, reject_note: bool = False) -> None:
        self.calls: list[dict] = []
        self.reject_note = reject_note

    def __call__(self, path, headers, payload, timeout):
        del path, headers, timeout
        self.calls.append(payload)
        stage = payload["messages"][0]["content"]
        reject = self.reject_note and stage.startswith(
            "commitloop-review-deterministic-note.v2"
        )
        content = {
            "faithful": not reject,
            "executable": True,
            "future_leakage": reject,
            "issues": ["future leakage"] if reject else [],
        }
        return {
            "model": REPORTED_MODEL_ID_BY_REQUESTED[payload["model"]],
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


def _case_and_events():
    token, events = ingest_bundle(
        synthetic_bundle("generation-fixture", "generation"),
        fhir_version="R4",
        ingested_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    return mine_candidates(token, events)[0], events


def _client(transport: GenerationFakeTransport) -> EvaluationClient:
    return EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-only-token",
        transport=transport,
        limits=RunLimits(max_requests=10),
    )


def test_typed_generation_is_source_bound_reviewed_and_gold_free() -> None:
    transport = GenerationFakeTransport()
    case, events = _case_and_events()
    result = construct_with_model_review(
        case=case,
        events=events,
        generator=_client(transport),
        reviewer=_client(transport),
    )
    assert result["status"] == "ACCEPTED"
    assert result["synthetic_note"] == render_anchor_note(case)
    assert result["clinical_adjudication"] == "NOT_RUN"
    assert result["construction_mode"] == (
        "deterministic_projection_with_dual_model_review"
    )
    assert len(result["stages"]) == len(transport.calls) == 2
    assert "gold" not in json.dumps(result).lower()
    first_payload = json.loads(transport.calls[0]["messages"][1]["content"])
    assert first_payload["deterministic_predicate"] == case.fulfillment_predicate
    assert first_payload["deterministic_candidate"] == result["candidate"]
    assert all(
        call["response_format"]["json_schema"]["name"]
        == "commitloop_nonclinical_review_v1"
        for call in transport.calls
    )
    assert all(
        item["reported_model_id"]
        == REPORTED_MODEL_ID_BY_REQUESTED[item["requested_model_id"]]
        for item in result["stages"]
    )


def test_deterministic_pipeline_rejects_negative_note_review() -> None:
    transport = GenerationFakeTransport(reject_note=True)
    case, events = _case_and_events()
    with pytest.raises(ValueError, match="model_assisted_item_rejected"):
        construct_with_model_review(
            case=case,
            events=events,
            generator=_client(transport),
            reviewer=_client(transport),
        )
