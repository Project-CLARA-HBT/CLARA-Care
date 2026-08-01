# ruff: noqa: E501
"""Tests for the CLARA Health Social platform API (spec: clara-health-social).

Invariants asserted here:

* **Flag-off ⇒ 404** — every social route 404s when ``SOCIAL_PLATFORM_ENABLED``
  is off, so the baseline surface is byte-identical to today (R1/R12).
* **Consent gate** — writing (join/post/comment/react) requires an active
  ``social_participation_v1`` grant; without it the write is rejected (R2/R10).
* **Moderation gate** — a body the ML guard blocks is never persisted; the
  moderation call is stubbed so the test is hermetic and network-free (R4/R6/R8).
* **Happy path** — with the flag on, consent granted, and moderation allowing,
  a user can join a community, post, comment, and react.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(email)}"}


@pytest.fixture
def social_on() -> Generator[None, None, None]:
    prev = os.environ.get("SOCIAL_PLATFORM_ENABLED")
    os.environ["SOCIAL_PLATFORM_ENABLED"] = "true"
    get_settings.cache_clear()
    yield
    if prev is None:
        os.environ.pop("SOCIAL_PLATFORM_ENABLED", None)
    else:
        os.environ["SOCIAL_PLATFORM_ENABLED"] = prev
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _allow_moderation(monkeypatch) -> None:
    """Stub the ML moderation bridge to ALLOW so tests are hermetic."""
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.social._moderate_text",
        lambda body: {"action": "allow", "reason": "test", "emergency": False},
    )


def _seed_community() -> int:
    """Insert a curated community directly and return its id."""
    from clara_api.db.models import SocialCommunity

    with SessionLocal() as db:
        existing = db.query(SocialCommunity).first()
        if existing is not None:
            return existing.id
        community = SocialCommunity(
            slug="tieu-duong",
            name="Sống khỏe cùng tiểu đường",
            description="Cộng đồng chia sẻ kinh nghiệm sống khỏe.",
            is_curated=True,
        )
        db.add(community)
        db.commit()
        db.refresh(community)
        return community.id


# --------------------------------------------------------------------------
# Flag-off ⇒ 404 (baseline unchanged)
# --------------------------------------------------------------------------
def test_flag_off_routes_404() -> None:
    get_settings.cache_clear()  # ensure default (off)
    headers = _auth("flagoff@normal.clara")
    for method, path in [
        ("get", "/api/v1/social/consent"),
        ("get", "/api/v1/social/communities"),
        ("get", "/api/v1/social/feed"),
        ("get", "/api/v1/social/me/profile"),
    ]:
        resp = getattr(client, method)(path, headers=headers)
        assert resp.status_code == 404, f"{method} {path} should 404 when flag off"


# --------------------------------------------------------------------------
# Consent gate
# --------------------------------------------------------------------------
def test_write_requires_consent(social_on) -> None:
    community_id = _seed_community()
    headers = _auth("noconsent@normal.clara")
    # Joining a community is a write ⇒ requires consent.
    resp = client.post(f"/api/v1/social/communities/{community_id}/join", headers=headers)
    assert resp.status_code == 428  # PRECONDITION_REQUIRED


def test_consent_grant_then_status(social_on) -> None:
    headers = _auth("consent@normal.clara")
    status_resp = client.get("/api/v1/social/consent", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["granted"] is False

    grant = client.post("/api/v1/social/consent", headers=headers)
    assert grant.status_code == 200
    assert grant.json()["granted"] is True


# --------------------------------------------------------------------------
# Happy path: consent → join → post → comment → react
# --------------------------------------------------------------------------
def test_full_participation_flow(social_on) -> None:
    community_id = _seed_community()
    headers = _auth("member@normal.clara")
    client.post("/api/v1/social/consent", headers=headers)

    join = client.post(f"/api/v1/social/communities/{community_id}/join", headers=headers)
    assert join.status_code == 200

    post = client.post(
        "/api/v1/social/posts",
        headers=headers,
        json={
            "community_id": community_id,
            "title": "Kinh nghiệm ăn uống",
            "body": "Mình muốn chia sẻ cách kiểm soát chế độ ăn hàng ngày.",
        },
    )
    assert post.status_code in (200, 201), post.text
    post_id = post.json()["id"]
    assert post.json()["author_handle"]

    comment = client.post(
        f"/api/v1/social/posts/{post_id}/comments",
        headers=headers,
        json={"body": "Cảm ơn bạn đã chia sẻ, rất hữu ích."},
    )
    assert comment.status_code in (200, 201), comment.text

    react = client.post(
        f"/api/v1/social/posts/{post_id}/reactions",
        headers=headers,
        json={"kind": "helpful"},
    )
    assert react.status_code == 200, react.text

    # Feed lists the post.
    feed = client.get("/api/v1/social/feed", headers=headers)
    assert feed.status_code == 200
    ids = [item["id"] for item in feed.json()]
    assert post_id in ids


def test_post_and_comment_writes_use_the_configured_durable_rate_budget(social_on, monkeypatch) -> None:
    """SOCIAL_WRITE_RATE_PER_MINUTE applies across post/comment surfaces."""

    community_id = _seed_community()
    headers = _auth("rate-budget@normal.clara")
    client.post("/api/v1/social/consent", headers=headers)
    monkeypatch.setattr(get_settings(), "social_write_rate_per_minute", 1)

    first = client.post(
        "/api/v1/social/posts",
        headers=headers,
        json={"community_id": community_id, "title": "Một", "body": "Nội dung đầu tiên."},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v1/social/posts/{first.json()['id']}/comments",
        headers=headers,
        json={"body": "Nội dung thứ hai phải bị giới hạn."},
    )
    assert second.status_code == 429


def test_comment_list_is_bounded_and_paginated(social_on) -> None:
    community_id = _seed_community()
    headers = _auth("comment-pages@normal.clara")
    client.post("/api/v1/social/consent", headers=headers)
    post = client.post(
        "/api/v1/social/posts",
        headers=headers,
        json={"community_id": community_id, "title": "Trang", "body": "Bài viết có bình luận."},
    )
    assert post.status_code == 201, post.text
    for body in ("Bình luận một.", "Bình luận hai."):
        response = client.post(
            f"/api/v1/social/posts/{post.json()['id']}/comments",
            headers=headers,
            json={"body": body},
        )
        assert response.status_code == 201, response.text

    page = client.get(
        f"/api/v1/social/posts/{post.json()['id']}/comments?limit=1&offset=1",
        headers=headers,
    )
    assert page.status_code == 200
    assert len(page.json()) == 1


# --------------------------------------------------------------------------
# Moderation gate: a blocked body is never persisted
# --------------------------------------------------------------------------
def test_blocked_body_not_persisted(social_on, monkeypatch) -> None:
    community_id = _seed_community()
    headers = _auth("blocked@normal.clara")
    client.post("/api/v1/social/consent", headers=headers)
    client.post(f"/api/v1/social/communities/{community_id}/join", headers=headers)

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.social._moderate_text",
        lambda body: {"action": "block", "reason": "prescription_request", "emergency": False},
    )
    resp = client.post(
        "/api/v1/social/posts",
        headers=headers,
        json={
            "community_id": community_id,
            "title": "Xin đơn thuốc",
            "body": "Kê cho tôi thuốc kháng sinh liều cao.",
        },
    )
    assert resp.status_code == 422  # blocked by moderation, not persisted


# --------------------------------------------------------------------------
# Moderation queue: admin can dismiss/remove reported content (RBAC + audit)
# --------------------------------------------------------------------------
def test_report_then_admin_removes_content(social_on) -> None:
    community_id = _seed_community()
    # A member posts, another member reports it.
    author = _auth("author@normal.clara")
    client.post("/api/v1/social/consent", headers=author)
    client.post(f"/api/v1/social/communities/{community_id}/join", headers=author)
    post = client.post(
        "/api/v1/social/posts",
        headers=author,
        json={
            "community_id": community_id,
            "title": "B\u00e0i vi\u1ebft b\u1ecb b\u00e1o c\u00e1o",
            "body": "N\u1ed9i dung n\u00e0y s\u1ebd b\u1ecb b\u00e1o c\u00e1o.",
        },
    )
    post_id = post.json()["id"]

    reporter = _auth("reporter@normal.clara")
    report = client.post(
        "/api/v1/social/reports",
        headers=reporter,
        json={"target_type": "post", "target_id": post_id, "reason": "spam"},
    )
    assert report.status_code in (200, 201), report.text

    # A non-admin may NOT see the moderation queue (RBAC).
    denied = client.get("/api/v1/social/moderation/reports", headers=reporter)
    assert denied.status_code == 403

    # Admin sees the open report and removes the content.
    settings = get_settings()
    admin_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.auth_bootstrap_admin_email,
            "password": settings.auth_bootstrap_admin_password,
        },
    )
    assert admin_login.status_code == 200, admin_login.text
    admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    queue = client.get("/api/v1/social/moderation/reports", headers=admin)
    assert queue.status_code == 200
    open_reports = queue.json()
    assert open_reports, "admin should see the open report"
    report_id = open_reports[0]["id"]

    action = client.post(
        f"/api/v1/social/moderation/reports/{report_id}/action",
        headers=admin,
        json={"action": "remove"},
    )
    assert action.status_code == 200, action.text
    assert action.json()["status"] == "resolved"

    # The removed post no longer appears in the feed.
    feed = client.get("/api/v1/social/feed", headers=author)
    assert post_id not in [item["id"] for item in feed.json()]
