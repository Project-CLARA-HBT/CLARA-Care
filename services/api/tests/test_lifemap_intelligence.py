from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import (
    AIContextManifest,
    FamilyAccessGrant,
    MLInferenceManifest,
    PhrProfile,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.intelligence import (
    EvidenceRow,
    deterministic_answer,
    hierarchical_summary,
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


def test_verifier_rejects_unsupported_or_hidden_ambiguity() -> None:
    row = EvidenceRow(
        evidence_id="ev:r1",
        revision_id="r1",
        event_id="e1",
        event_type="symptom",
        occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
        recorded_at=datetime(2026, 7, 29, 1, tzinfo=UTC),
        truth_state="disputed",
        source_kind="reported",
        attribution="user_report",
        text="Đau đầu nhẹ",
    )
    unsupported = {
        "claims": [{"text": "Chẩn đoán migraine", "citation_ids": ["ev:r1"]}],
        "disputed": ["ev:r1"],
        "conflicting": [],
    }
    with pytest.raises(ValueError, match="claim_not_entailed"):
        verify_grounded_answer(unsupported, [row])
    hidden = {
        "claims": [{"text": "Đau đầu nhẹ", "citation_ids": ["ev:r1"]}],
        "disputed": [],
        "conflicting": [],
    }
    with pytest.raises(ValueError, match="not_surfaced"):
        verify_grounded_answer(hidden, [row])


def test_empty_evidence_abstains_instead_of_inventing() -> None:
    result = deterministic_answer(intent="timeline_lookup", evidence=[], locale="vi")
    assert result["status"] == "abstained"
    assert result["claims"] == []
    assert result["abstention_code"] == "insufficient_information"


def test_generated_medication_fragment_requires_fides_pass() -> None:
    row = EvidenceRow(
        evidence_id="ev:med",
        revision_id="med",
        event_id="event-med",
        event_type="medication_report",
        occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
        recorded_at=datetime(2026, 7, 29, tzinfo=UTC),
        truth_state="confirmed",
        source_kind="document",
        attribution="source_document",
        text="Nhãn nguồn ghi 5 mg",
    )
    answer = {
        "claims": [{"text": "5 mg", "citation_ids": ["ev:med"]}],
        "disputed": [],
        "conflicting": [],
    }
    with pytest.raises(ValueError, match="fides_required"):
        verify_grounded_answer(answer, [row])
    assert verify_grounded_answer(answer, [row], fides_verdict="pass")["fides"] == "pass"


def test_hierarchical_summary_preserves_order_truth_and_exact_citations() -> None:
    rows = [
        EvidenceRow(
            evidence_id=f"ev:r{index}",
            revision_id=f"r{index}",
            event_id=f"e{index}",
            event_type="symptom_report",
            occurred_at=datetime(2026, 7, 28 + index, 8, tzinfo=UTC),
            recorded_at=datetime(2026, 7, 28 + index, 9, tzinfo=UTC),
            truth_state="disputed" if index == 1 else "confirmed",
            source_kind="reported",
            attribution="user_report",
            text=f"claim {index}",
        )
        for index in (0, 1)
    ]
    summary = hierarchical_summary(rows[::-1], level="day", locale="vi")
    children = summary["children"]
    assert isinstance(children, list)
    assert [item["claims"][0]["citation_ids"] for item in children] == [
        ["ev:r0"],
        ["ev:r1"],
    ]
    assert summary["disputed"] == ["ev:r1"]
    assert summary["fallback_used"] is True


def test_ask_endpoint_is_revision_cited_and_persists_private_lineage(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_ask_ai_enabled", True)
    monkeypatch.setattr(get_settings(), "lifemap_ai_summaries_enabled", True)
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
    summary = client.get(
        "/api/v1/lifemap/v2/summaries/day",
        headers=headers,
    )
    assert summary.status_code == 200
    assert summary.json()["input_revision_ids"] == [
        row["revision_id"] for row in body["evidence"]
    ]
    assert summary.json()["disclosure"]["preserves_truth_state"] is True

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


def test_delegated_digest_rechecks_grant_and_withholds_unrequested_types(
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_ai_summaries_enabled", True)
    owner_headers = _account()
    with SessionLocal() as db:
        owner_profile = db.execute(
            select(PhrProfile).order_by(PhrProfile.id.desc())
        ).scalars().first()
        assert owner_profile is not None
        owner_profile_id = owner_profile.public_id
    created = client.post(
        "/api/v1/lifemap/events",
        headers={**owner_headers, "Idempotency-Key": uuid4().hex},
        json={
            "event_type": "sleep_report",
            "occurred_at": "2026-07-29T08:00:00Z",
            "payload": {"hours": 7},
            "truth_state": "confirmed",
        },
    )
    assert created.status_code == 201
    caregiver_headers = _account()
    now = datetime.now(UTC)
    with SessionLocal() as db:
        caregiver_profile = db.execute(
            select(PhrProfile).order_by(PhrProfile.id.desc())
        ).scalars().first()
        owner_profile = db.execute(
            select(PhrProfile).where(PhrProfile.public_id == owner_profile_id)
        ).scalar_one()
        assert caregiver_profile is not None
        grant = FamilyAccessGrant(
            profile_id=owner_profile.id,
            grantor_user_id=owner_profile.user_id,
            grantee_user_id=caregiver_profile.user_id,
            object_type="lifemap",
            object_id=owner_profile.public_id,
            allowed_actions_json=["view"],
            data_classes_json=["lifemap"],
            purpose="care_coordination",
            status="active",
            starts_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(days=1),
        )
        db.add(grant)
        db.commit()
        grant_id = grant.id
    digest = client.get(
        "/api/v1/lifemap/v2/digests/day",
        headers={
            **caregiver_headers,
            "X-CLARA-Profile-Context": owner_profile_id,
        },
        params={
            "purpose": "care_coordination",
            "event_types": "symptom_report",
        },
    )
    assert digest.status_code == 200, digest.text
    assert digest.json()["input_revision_ids"] == []
    assert digest.json()["withheld_event_types"] == ["symptom_report"]
    with SessionLocal() as db:
        grant = db.get(FamilyAccessGrant, grant_id)
        assert grant is not None
        grant.status = "revoked"
        grant.revoked_at = datetime.now(UTC)
        db.commit()
    denied = client.get(
        "/api/v1/lifemap/v2/digests/day",
        headers={
            **caregiver_headers,
            "X-CLARA-Profile-Context": owner_profile_id,
        },
        params={"purpose": "care_coordination"},
    )
    assert denied.status_code == 404
