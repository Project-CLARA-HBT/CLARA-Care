"""Revision-aware Replay and episode-goal command contracts."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import (
    LifeMapEpisode,
    LifeMapEpisodeEventLink,
    LifeMapEpisodeGoalRevision,
    LifeMapEvent,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account() -> dict[str, str]:
    suffix = uuid4().hex
    login = client.post(
        "/api/v1/auth/login",
        json={"email": f"replay-v2-{suffix}@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Replay V2"},
        ).status_code
        == 200
    )
    return headers


def test_goal_history_and_correction_move_replay_to_exact_revision() -> None:
    headers = _account()
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"title": "Theo dõi giấc ngủ", "goal": "Ghi nhận 3 ngày"},
    )
    assert episode.status_code == 201
    episode_id = episode.json()["id"]

    revised = client.post(
        f"/api/v1/lifemap/episodes/{episode_id}/goal",
        headers={
            **headers,
            "Idempotency-Key": uuid4().hex,
            "If-Match": "1",
        },
        json={"goal": "Ghi nhận 7 ngày", "reason": "Cần thêm dữ liệu"},
    )
    assert revised.status_code == 200
    assert revised.json()["version"] == 2

    event = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={
            "event_type": "sleep_note",
            "occurred_at": "2026-07-28T08:00:00Z",
            "payload": {"hours": 5},
            "episode_id": episode_id,
        },
    )
    assert event.status_code == 201
    corrected = client.post(
        f"/api/v1/lifemap/events/{event.json()['id']}/correct",
        headers={
            **headers,
            "Idempotency-Key": uuid4().hex,
            "If-Match": "1",
        },
        json={"payload": {"hours": 6}, "reason": "Nhập nhầm"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["revision"] == 2

    replay = client.get(f"/api/v1/episodes/{episode_id}/replay", headers=headers)
    assert replay.status_code == 200
    fact = replay.json()["events"][0]
    assert fact["id"] == event.json()["id"]
    assert fact["revision"] == 2
    assert fact["truth_state"] == "user_reported"
    assert fact["policy_version"] == "lifemap-truth-v2"
    assert fact["why"]["code"] == "Nhập nhầm"

    with SessionLocal() as db:
        stored_episode = db.execute(
            select(LifeMapEpisode).where(LifeMapEpisode.public_id == episode_id)
        ).scalar_one()
        goals = list(
            db.execute(
                select(LifeMapEpisodeGoalRevision)
                .where(LifeMapEpisodeGoalRevision.episode_id == stored_episode.id)
                .order_by(LifeMapEpisodeGoalRevision.revision_no)
            ).scalars()
        )
        assert [(row.revision_no, row.goal) for row in goals] == [
            (1, "Ghi nhận 3 ngày"),
            (2, "Ghi nhận 7 ngày"),
        ]
        stored_event = db.execute(
            select(LifeMapEvent).where(LifeMapEvent.public_id == event.json()["id"])
        ).scalar_one()
        links = list(
            db.execute(
                select(LifeMapEpisodeEventLink)
                .where(LifeMapEpisodeEventLink.event_id == stored_event.id)
                .order_by(LifeMapEpisodeEventLink.id)
            ).scalars()
        )
        assert [link.status for link in links] == ["superseded", "active"]


def test_goal_command_rejects_stale_version() -> None:
    headers = _account()
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"title": "Theo dõi vận động"},
    )
    response = client.post(
        f"/api/v1/lifemap/episodes/{episode.json()['id']}/goal",
        headers={
            **headers,
            "Idempotency-Key": uuid4().hex,
            "If-Match": "9",
        },
        json={"goal": "Đi bộ đều"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_version"
