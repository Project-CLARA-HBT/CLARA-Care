"""Focused contracts for the server-backed LifeMap episode guided flow."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response as HttpxResponse
from sqlalchemy import select

from clara_api.api.v1.endpoints import guided_flows
from clara_api.db.models import (
    GuidedFlowDraft,
    LifeMapCommandRecord,
    LifeMapEpisode,
    LifeMapEpisodeGoalRevision,
    LifeMapOutboxEvent,
    PhrAudit,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account(label: str) -> dict[str, str]:
    suffix = uuid4().hex
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"guided-{label}-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile = client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": f"Guided {label}"},
    )
    assert profile.status_code == 200
    return headers


def _create(
    headers: dict[str, str],
    *,
    key: str,
    title: str = "Theo dõi giấc ngủ",
    current_step: str = "title",
) -> HttpxResponse:
    return client.post(
        "/api/v1/guided-flows",
        headers={**headers, "Idempotency-Key": key},
        json={
            "flow_type": "lifemap_episode",
            "current_step": current_step,
            "payload": {"title": title},
        },
    )


def test_guided_flow_create_is_typed_idempotent_and_owner_scoped() -> None:
    owner = _account("owner")
    stranger = _account("stranger")
    key = f"create-{uuid4().hex}"

    created = _create(owner, key=key)
    assert created.status_code == 201
    assert created.headers["etag"] == '"1"'
    assert created.headers["cache-control"] == "private, no-store"
    body = created.json()
    assert body["flow_type"] == "lifemap_episode"
    assert body["payload"] == {"title": "Theo dõi giấc ngủ", "goal": None, "priority": None}
    draft_id = body["id"]
    assert draft_id.isdecimal() is False

    replay = _create(owner, key=key)
    assert replay.status_code == 201
    assert replay.json()["id"] == draft_id
    assert replay.headers["cache-control"] == "private, no-store"

    conflict = _create(owner, key=key, title="Nội dung khác")
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"

    unknown = client.post(
        "/api/v1/guided-flows",
        headers={**owner, "Idempotency-Key": uuid4().hex},
        json={
            "flow_type": "lifemap_episode",
            "payload": {"title": "Hợp lệ", "diagnosis": "not allowed"},
        },
    )
    assert unknown.status_code == 422
    assert _create(owner, key="short").status_code == 422

    owner_read = client.get(f"/api/v1/guided-flows/{draft_id}", headers=owner)
    assert owner_read.status_code == 200
    assert owner_read.headers["cache-control"] == "private, no-store"
    assert client.get(f"/api/v1/guided-flows/{draft_id}", headers=stranger).status_code == 404
    active = client.get(
        "/api/v1/guided-flows",
        params={"flow_type": "lifemap_episode"},
        headers=owner,
    )
    assert active.status_code == 200
    assert active.headers["cache-control"] == "private, no-store"
    assert [item["id"] for item in active.json()["items"]] == [draft_id]


def test_guided_flow_update_commit_and_replay_preserve_lifemap_invariants() -> None:
    headers = _account("commit")
    create_key = f"create-{uuid4().hex}"
    created = _create(headers, key=create_key)
    draft_id = created.json()["id"]

    missing_match = client.patch(
        f"/api/v1/guided-flows/{draft_id}",
        headers=headers,
        json={"current_step": "goal", "payload": {"goal": "Ngủ đều hơn"}},
    )
    assert missing_match.status_code == 422

    updated = client.patch(
        f"/api/v1/guided-flows/{draft_id}",
        headers={**headers, "If-Match": '"1"'},
        json={
            "current_step": "review",
            "payload": {"goal": "Ngủ đều hơn", "priority": "soon"},
        },
    )
    assert updated.status_code == 200
    assert updated.headers["etag"] == '"2"'
    assert updated.headers["cache-control"] == "private, no-store"
    assert updated.json()["payload"] == {
        "title": "Theo dõi giấc ngủ",
        "goal": "Ngủ đều hơn",
        "priority": "soon",
    }

    stale = client.patch(
        f"/api/v1/guided-flows/{draft_id}",
        headers={**headers, "If-Match": '"1"'},
        json={"current_step": "review", "payload": {}},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == {
        "code": "stale_revision",
        "current_revision": 2,
    }

    commit_key = f"commit-{uuid4().hex}"
    committed = client.post(
        f"/api/v1/guided-flows/{draft_id}/commit",
        headers={
            **headers,
            "If-Match": '"2"',
            "Idempotency-Key": commit_key,
        },
    )
    assert committed.status_code == 201
    assert committed.headers["etag"] == '"3"'
    assert committed.headers["cache-control"] == "private, no-store"
    committed_body = committed.json()
    assert committed_body["status"] == "committed"
    episode_id = committed_body["committed_resource"]["id"]
    assert committed_body["committed_resource"]["type"] == "lifemap_episode"

    replay = client.post(
        f"/api/v1/guided-flows/{draft_id}/commit",
        headers={
            **headers,
            "If-Match": '"2"',
            "Idempotency-Key": commit_key,
        },
    )
    assert replay.status_code == 201
    assert replay.headers["cache-control"] == "private, no-store"
    assert replay.json()["committed_resource"]["id"] == episode_id

    with SessionLocal() as db:
        episode = db.execute(
            select(LifeMapEpisode).where(LifeMapEpisode.public_id == episode_id)
        ).scalar_one()
        assert episode.title == "Theo dõi giấc ngủ"
        assert episode.goal == "Ngủ đều hơn"
        assert episode.priority == "soon"
        assert episode.status == "open"
        assert episode.version_no == 1
        revisions = list(
            db.execute(
                select(LifeMapEpisodeGoalRevision).where(
                    LifeMapEpisodeGoalRevision.episode_id == episode.id
                )
            ).scalars()
        )
        assert len(revisions) == 1
        assert revisions[0].revision_no == 1
        assert revisions[0].goal == episode.goal

        command_rows = list(
            db.execute(
                select(LifeMapCommandRecord).where(
                    LifeMapCommandRecord.operation.like("guided_flow.%")
                )
            ).scalars()
        )
        relevant = [
            row
            for row in command_rows
            if row.response_json.get("id") == draft_id
        ]
        assert len(relevant) == 2
        serialized_commands = json.dumps(
            [row.response_json for row in relevant], ensure_ascii=False
        )
        assert "Theo dõi" not in serialized_commands
        assert "Ngủ đều" not in serialized_commands
        assert "payload" not in serialized_commands

        audits = list(
            db.execute(
                select(PhrAudit).where(
                    PhrAudit.entity.in_(("guided_flow_draft", "episode")),
                    PhrAudit.entity_id.in_((draft_id, episode_id)),
                )
            ).scalars()
        )
        assert audits
        assert all(row.before_json is None and row.after_json is None for row in audits)
        outbox = db.execute(
            select(LifeMapOutboxEvent).where(
                LifeMapOutboxEvent.aggregate_id == episode_id
            )
        ).scalar_one()
        assert outbox.payload_json == {
            "aggregate_id": episode_id,
            "event_type": "lifemap.episode.created",
        }

    assert client.get("/api/v1/guided-flows", headers=headers).json()["items"] == []


def test_guided_flow_expiry_and_abandon_remove_drafts_from_resume_list() -> None:
    headers = _account("lifecycle")
    expired = _create(headers, key=uuid4().hex)
    expired_id = expired.json()["id"]
    with SessionLocal() as db:
        row = db.execute(
            select(GuidedFlowDraft).where(GuidedFlowDraft.public_id == expired_id)
        ).scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    gone = client.get(f"/api/v1/guided-flows/{expired_id}", headers=headers)
    assert gone.status_code == 410
    assert gone.json()["detail"]["code"] == "guided_flow_expired"
    expired_update = client.patch(
        f"/api/v1/guided-flows/{expired_id}",
        headers={**headers, "If-Match": '"1"'},
        json={"current_step": "goal", "payload": {}},
    )
    assert expired_update.status_code == 410

    active = _create(headers, key=uuid4().hex)
    active_id = active.json()["id"]
    abandoned = client.post(
        f"/api/v1/guided-flows/{active_id}/abandon",
        headers={**headers, "If-Match": '"1"'},
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["status"] == "abandoned"
    assert abandoned.headers["etag"] == '"2"'
    assert abandoned.headers["cache-control"] == "private, no-store"
    resumed = client.get("/api/v1/guided-flows", headers=headers)
    assert resumed.status_code == 200
    assert resumed.headers["cache-control"] == "private, no-store"
    assert resumed.json()["items"] == []


def test_guided_flow_commit_is_atomic_when_command_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _account("atomic")
    title = f"Atomic {uuid4().hex}"
    created = _create(
        headers,
        key=uuid4().hex,
        title=title,
        current_step="review",
    )
    draft_id = created.json()["id"]

    def _fail_store(*args, **kwargs):
        raise RuntimeError("forced command failure")

    monkeypatch.setattr(guided_flows, "store_command", _fail_store)
    with pytest.raises(RuntimeError, match="forced command failure"):
        client.post(
            f"/api/v1/guided-flows/{draft_id}/commit",
            headers={
                **headers,
                "If-Match": '"1"',
                "Idempotency-Key": uuid4().hex,
            },
        )

    with SessionLocal() as db:
        draft = db.execute(
            select(GuidedFlowDraft).where(GuidedFlowDraft.public_id == draft_id)
        ).scalar_one()
        assert draft.status == "active"
        assert draft.revision == 1
        assert (
            db.execute(
                select(LifeMapEpisode).where(LifeMapEpisode.title == title)
            ).scalar_one_or_none()
            is None
        )
