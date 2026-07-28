"""Server-authoritative Phase 6 flag, consent, and command contracts."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import (
    LifeMapBaselineDefinition,
    LifeMapQuestionDefinition,
    PhrProfile,
    WearableDailyAggregate,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account(*, consent: bool) -> tuple[dict[str, str], int]:
    suffix = uuid4().hex
    login = client.post(
        "/api/v1/auth/login",
        json={"email": f"phase6-{suffix}@example.com", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": "Phase 6"},
    ).status_code == 200
    if consent:
        status = client.get("/api/v1/auth/consent-status", headers=headers).json()
        assert client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": status["required_version"]},
        ).status_code == 200
    profile_id = client.get("/api/v1/profiles", headers=headers).json()[0]["id"]
    with SessionLocal() as db:
        internal_id = db.execute(
            select(PhrProfile.id).where(PhrProfile.public_id == profile_id)
        ).scalar_one()
    return headers, internal_id


def test_baseline_v2_requires_current_consent_and_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_baselines_v2_enabled", True)
    no_consent, _ = _account(consent=False)
    assert (
        client.get("/api/v1/lifemap/v2/baselines", headers=no_consent).status_code
        == 428
    )

    headers, profile_id = _account(consent=True)
    suffix = uuid4().hex
    signal = f"phase6_{suffix}"
    with SessionLocal() as db:
        definition = LifeMapBaselineDefinition(
            signal_key=signal,
            version="test-v1",
            canonical_unit="count",
            valid_min=0,
            valid_max=100_000,
            minimum_samples=7,
            minimum_span_days=7,
            window_days=28,
            source_eligibility_json={"origins": ["test"]},
            exclusions_json=[],
            change_rules_json={"relative_threshold": 0.2},
            status="approved",
            approved_by="test",
            approved_at=datetime.now(UTC),
        )
        db.add(definition)
        today = datetime.now(UTC).date()
        db.add_all(
            [
                WearableDailyAggregate(
                    profile_id=profile_id,
                    record_type=signal,
                    local_date=today - timedelta(days=6 - index),
                    value_json={"scalar": 1000 + index, "unit": "count"},
                    primary_origin="test",
                    policy_version="test-v1",
                )
                for index in range(7)
            ]
        )
        db.commit()

    key = uuid4().hex
    first = client.post(
        f"/api/v1/lifemap/v2/baselines/{signal}/recompute",
        headers={**headers, "Idempotency-Key": key},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "ready"
    assert first.json()["idempotent_replay"] is False
    replay = client.post(
        f"/api/v1/lifemap/v2/baselines/{signal}/recompute",
        headers={**headers, "Idempotency-Key": key},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["idempotent_replay"] is True


def test_governed_question_records_burden_and_then_asks_nothing(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "lifemap_next_question_v2_enabled", True)
    monkeypatch.setattr(settings, "lifemap_capture_enabled", True)
    headers, _profile_id = _account(consent=True)
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"title": "General wellness check"},
    ).json()
    with SessionLocal() as db:
        question = LifeMapQuestionDefinition(
            field_key=f"general_{uuid4().hex}",
            version="test-v1",
            locale="vi",
            episode_class="general",
            question_text="Bạn muốn bổ sung điều gì?",
            rationale_text="Giúp hoàn thiện bản ghi do bạn kiểm soát.",
            sensitivity="standard",
            answer_schema_json={"type": "object"},
            impact_weight=1,
            impact_mapping_json={},
            status="approved",
            approved_by="test",
            approved_at=datetime.now(UTC),
        )
        db.add(question)
        db.commit()
        question_id = question.public_id

    offered = client.get(
        f"/api/v1/episodes/{episode['id']}/next-question?locale=vi",
        headers=headers,
    )
    assert offered.status_code == 200, offered.text
    assert offered.json()["question_id"] == question_id
    recorded = client.post(
        f"/api/v1/episodes/{episode['id']}/questions/{question_id}/interaction",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"action": "presented", "reason": ""},
    )
    assert recorded.status_code == 200
    second = client.get(
        f"/api/v1/episodes/{episode['id']}/next-question?locale=vi",
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["ask"] is False
    assert second.json()["reason_code"] == "burden_budget_exhausted"
