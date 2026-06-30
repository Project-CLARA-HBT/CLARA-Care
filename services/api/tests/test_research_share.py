"""Tests for the research read-only share endpoint (clara-research R16.3, task 17.2).

Covers the ``POST /research/tier2/jobs/{job_id}/share`` flag gate (default-off →
404), owner isolation, and that the reused ``WorkspaceConversationShare``
mechanism produces a ``share_token`` and a ``/share/{token}`` public URL.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ResearchJob, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _enable_share(monkeypatch, value: bool = True) -> None:
    monkeypatch.setattr(get_settings(), "research_share_enabled", value, raising=False)


def _seed_job(*, email: str, job_id: str, status: str = "completed") -> None:
    now = datetime.now(tz=UTC)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        job = ResearchJob(
            job_id=job_id,
            user_id=user.id,
            role="researcher",
            status=status,
            query_text="metformin vs insulin",
            request_payload={"query": "metformin vs insulin", "research_mode": "deep"},
            progress_json={
                "flow_events": [],
                "flow_stages": [],
                "active_stage": "",
                "status_note": "",
                "reasoning_steps": [],
            },
            result_json={"tier": "tier2", "answer_markdown": "## Kết luận"},
            error_text="",
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now if status == "completed" else None,
        )
        db.add(job)
        db.commit()


def test_share_flag_off_returns_404(monkeypatch) -> None:
    _enable_share(monkeypatch, value=False)
    token = _login("share.flagoff@research.clara")
    _seed_job(email="share.flagoff@research.clara", job_id="share-flag-off")
    response = client.post(
        "/api/v1/research/tier2/jobs/share-flag-off/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_share_creates_token_and_public_url(monkeypatch) -> None:
    _enable_share(monkeypatch)
    token = _login("share.create@research.clara")
    _seed_job(email="share.create@research.clara", job_id="share-create")
    resp = client.post(
        "/api/v1/research/tier2/jobs/share-create/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_id"] == "share-create"
    assert body["is_active"] is True
    assert body["share_token"]
    assert body["public_url"].endswith(f"/share/{body['share_token']}")


def test_share_is_idempotent_without_rotate(monkeypatch) -> None:
    _enable_share(monkeypatch)
    token = _login("share.idem@research.clara")
    _seed_job(email="share.idem@research.clara", job_id="share-idem")
    first = client.post(
        "/api/v1/research/tier2/jobs/share-idem/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/research/tier2/jobs/share-idem/share",
        headers={"Authorization": f"Bearer {token}"},
        json={"rotate": False},
    )
    assert second.status_code == 200, second.text
    assert first.json()["share_token"] == second.json()["share_token"]


def test_share_rotate_changes_token(monkeypatch) -> None:
    _enable_share(monkeypatch)
    token = _login("share.rotate@research.clara")
    _seed_job(email="share.rotate@research.clara", job_id="share-rotate")
    first = client.post(
        "/api/v1/research/tier2/jobs/share-rotate/share",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200, first.text
    rotated = client.post(
        "/api/v1/research/tier2/jobs/share-rotate/share",
        headers={"Authorization": f"Bearer {token}"},
        json={"rotate": True},
    )
    assert rotated.status_code == 200, rotated.text
    assert first.json()["share_token"] != rotated.json()["share_token"]


def test_share_owner_isolation(monkeypatch) -> None:
    _enable_share(monkeypatch)
    _login("share.owner@research.clara")
    _seed_job(email="share.owner@research.clara", job_id="share-owned")
    other_token = _login("share.intruder@research.clara")
    resp = client.post(
        "/api/v1/research/tier2/jobs/share-owned/share",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
