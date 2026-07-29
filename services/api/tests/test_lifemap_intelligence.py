from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import AIContextManifest, MLInferenceManifest
from clara_api.db.session import SessionLocal
from clara_api.lifemap.intelligence import (
    deterministic_answer,
    route_ask_query,
    verify_grounded_answer,
)
from clara_api.main import app

client = TestClient(app)


def _account() -> dict[str, str]:
    email = f"lifemap-ask-{uuid4().hex}@normal.clara"
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Ask LifeMap"},
        ).status_code
        == 200
    )
    status = client.get("/api/v1/auth/consent-status", headers=headers).json()
    accepted = client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"consent_version": status["required_version"]},
    )
    assert accepted.status_code == 200
    return headers


def test_safety_route_precedes_retrieval() -> None:
    assert route_ask_query("Tôi không thở được").emergency is True
    assert route_ask_query("Diagnose me from my timeline").blocked_reason == "legal_guard"
    assert route_ask_query("So sánh tuần này và tuần trước").intent == "comparison"


def test_verifier_rejects_citation_outside_evidence_table() -> None:
    answer = {
        "claims": [{"text": "unsupported", "citation_ids": ["ev:not-present"]}]
    }
    with pytest.raises(ValueError, match="citation_outside_evidence_table"):
        verify_grounded_answer(answer, [])


def test_empty_evidence_abstains_instead_of_inventing() -> None:
    result = deterministic_answer(intent="timeline_lookup", evidence=[], locale="vi")
    assert result["status"] == "abstained"
    assert result["claims"] == []
    assert result["abstention_code"] == "insufficient_information"


def test_ask_endpoint_is_revision_cited_and_persists_private_lineage(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_ask_ai_enabled", True)
    headers = _account()
    created = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={
            "event_type": "symptom_report",
            "occurred_at": "2026-07-28T08:00:00Z",
            "payload": {"summary": "Đau đầu nhẹ sau khi ngủ muộn"},
            "truth_state": "confirmed",
        },
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/api/v1/lifemap/v2/ask",
        headers=headers,
        json={"query": "Các ghi nhận đau đầu gần đây?", "locale": "vi"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "grounded"
    assert body["disclosure"]["mutates_lifemap"] is False
    assert body["verification"]["citation_existence"] == "pass"
    evidence_ids = {row["evidence_id"] for row in body["evidence"]}
    assert evidence_ids
    assert all(
        set(claim["citation_ids"]) <= evidence_ids for claim in body["claims"]
    )

    with SessionLocal() as db:
        context = db.execute(
            select(AIContextManifest).where(
                AIContextManifest.public_id == body["context_manifest_id"]
            )
        ).scalar_one()
        inference = db.execute(
            select(MLInferenceManifest).where(
                MLInferenceManifest.public_id == body["inference_manifest_id"]
            )
        ).scalar_one()
        assert context.profile_id > 0
        assert context.revision_refs_json == [
            row["revision_id"] for row in body["evidence"]
        ]
        assert inference.operational_json.keys() <= {
            "latency_ms",
            "input_revision_count",
            "citation_count",
            "abstained",
            "ood",
            "fallback_used",
            "locale",
        }


def test_emergency_fast_path_does_not_require_a_profile(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_ask_ai_enabled", True)
    email = f"lifemap-emergency-{uuid4().hex}@normal.clara"
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(
        "/api/v1/lifemap/v2/ask",
        headers=headers,
        json={"query": "Tôi không thở được", "locale": "vi"},
    )
    assert response.status_code == 200
    assert response.json()["verification"] == {"retrieval_bypassed": True}
