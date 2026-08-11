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
    def __init__(self, *, leak_note: bool = False) -> None:
        self.calls: list[dict] = []
        self.leak_note = leak_note

    def __call__(self, path, headers, payload, timeout):
        del path, headers, timeout
        self.calls.append(payload)
        stage = payload["messages"][0]["content"]
        source = json.loads(payload["messages"][1]["content"])
        if stage.startswith("commitloop-generation-candidate.v1"):
            content = source["anchor"]
        elif stage.startswith("commitloop-generation-predicate.v2"):
            content = {"predicate": source["allowed_predicate_projection"]}
        elif stage.startswith("commitloop-generation-anchor-note.v1"):
            content = {
                "note": (
                    source["allowed_note_projection"] + " later outcome"
                    if self.leak_note
                    else source["allowed_note_projection"]
                )
            }
        else:
            content = {
                "faithful": True,
                "executable": True,
                "future_leakage": False,
                "issues": [],
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
    assert len(result["stages"]) == len(transport.calls) == 5
    assert "gold" not in json.dumps(result).lower()
    predicate_payload = json.loads(transport.calls[1]["messages"][1]["content"])
    assert predicate_payload["allowed_predicate_projection"] == case.fulfillment_predicate
    assert all(
        item["reported_model_id"]
        == REPORTED_MODEL_ID_BY_REQUESTED[item["requested_model_id"]]
        for item in result["stages"]
    )


def test_deterministic_validator_rejects_future_note_even_after_positive_review() -> None:
    transport = GenerationFakeTransport(leak_note=True)
    case, events = _case_and_events()
    with pytest.raises(ValueError, match="generated_note_not_anchor_projection"):
        construct_with_model_review(
            case=case,
            events=events,
            generator=_client(transport),
            reviewer=_client(transport),
        )
