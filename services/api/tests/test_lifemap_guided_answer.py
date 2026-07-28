"""Governed questions route answers through Capture and explicit review."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import (
    LifeMapEvent,
    LifeMapQuestionDefinition,
    LifeMapQuestionInteraction,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account() -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"guided-{uuid4().hex}@example.com",
            "password": "secret123",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": "Guided Answer"},
    ).status_code == 200
    status = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"accepted": True, "consent_version": status["required_version"]},
    ).status_code == 200
    return headers


def test_guided_answer_is_draft_until_explicit_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_capture_enabled", True)
    headers = _account()
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"title": "Theo dõi sức khỏe"},
    ).json()
    field_key = f"test_answer_{uuid4().hex}"
    with SessionLocal() as db:
        question = LifeMapQuestionDefinition(
            field_key=field_key,
            version="test-v1",
            locale="vi",
            episode_class="test_only",
            question_text="Bạn cảm thấy thế nào?",
            rationale_text="Giúp ghi lại điều bạn chủ động chia sẻ.",
            answer_schema_json={"type": "object"},
            impact_weight=1,
            status="approved",
            approved_by="test",
            approved_at=datetime.now(UTC),
        )
        db.add(question)
        db.commit()
        question_id = question.public_id

    started = client.post(
        "/api/v1/lifemap/capture/guided-answers",
        headers=headers,
        json={
            "episode_id": episode["id"],
            "question_id": question_id,
            "answer": {"value": "Ổn hơn"},
        },
    )
    assert started.status_code == 201, started.text
    candidate = started.json()["candidates"][0]
    assert candidate["type"] == "guided_answer"
    with SessionLocal() as db:
        assert db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.event_type == field_key
            )
        ).first() is None

    confirmed = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate['id']}/review",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"action": "confirm", "reason": "Đã kiểm tra"},
    )
    assert confirmed.status_code == 200, confirmed.text
    with SessionLocal() as db:
        event = db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.public_id == confirmed.json()["event_id"]
            )
        ).scalar_one()
        assert event.episode_id is not None
        assert event.truth_state == "confirmed"
        actions = list(
            db.execute(
                select(LifeMapQuestionInteraction.action).where(
                    LifeMapQuestionInteraction.question_definition_id
                    == db.execute(
                        select(LifeMapQuestionDefinition.id).where(
                            LifeMapQuestionDefinition.public_id == question_id
                        )
                    ).scalar_one()
                )
            ).scalars()
        )
        assert actions == ["answered_draft", "confirmed"]
