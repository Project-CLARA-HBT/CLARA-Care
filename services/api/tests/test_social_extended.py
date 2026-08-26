# ruff: noqa: E501
"""Integration tests for extended social features.

Covers:
- Clinician verification on profiles and posts/comments
- Extended PostResponse and CommentResponse schemas
- Post search with text and community filter
- Post bookmarking toggle and listing user bookmarks
- Post deletion (author vs non-author vs admin)
- Comment deletion (author vs non-author vs admin)
- Community leave endpoint
- Threaded comments with parent_id
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import SocialCommunity
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
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


def _seed_community(slug: str = "dinh-duong", name: str = "Dinh Dưỡng & Sức Khỏe") -> int:
    with SessionLocal() as db:
        existing = db.query(SocialCommunity).filter(SocialCommunity.slug == slug).first()
        if existing is not None:
            return existing.id
        community = SocialCommunity(
            slug=slug,
            name=name,
            description="Cộng đồng chia sẻ kiến thức dinh dưỡng.",
            is_curated=True,
        )
        db.add(community)
        db.commit()
        db.refresh(community)
        return community.id


def test_verified_clinician_profile_and_post_metadata(social_on) -> None:
    community_id = _seed_community()
    # doctor role user
    doc_headers = _auth("doc1@doctor.clara")
    client.post("/api/v1/social/consent", headers=doc_headers)

    # Check profile
    profile_resp = client.get("/api/v1/social/me/profile", headers=doc_headers)
    assert profile_resp.status_code == 200
    assert profile_resp.json()["role_badge"] == "clinician"

    # Post by doctor
    post_resp = client.post(
        "/api/v1/social/posts",
        headers=doc_headers,
        json={
            "community_id": community_id,
            "title": "Lời khuyên từ bác sĩ",
            "body": "Uống đủ nước mỗi ngày rất quan trọng cho thận.",
        },
    )
    assert post_resp.status_code == 201
    pdata = post_resp.json()
    assert pdata["is_verified_clinician"] is True
    assert pdata["community_name"] == "Dinh Dưỡng & Sức Khỏe"
    assert pdata["comment_count"] == 0
    assert pdata["reaction_count"] == 0
    assert pdata["user_reaction"] is None
    assert pdata["is_bookmarked"] is False
    assert isinstance(pdata["reactions_breakdown"], dict)

    # Normal user views post
    user_headers = _auth("user1@normal.clara")
    client.post("/api/v1/social/consent", headers=user_headers)
    get_resp = client.get(f"/api/v1/social/posts/{pdata['id']}", headers=user_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["is_verified_clinician"] is True

    # Normal user comments
    comment_resp = client.post(
        f"/api/v1/social/posts/{pdata['id']}/comments",
        headers=user_headers,
        json={"body": "Cảm ơn bác sĩ!"},
    )
    assert comment_resp.status_code == 201
    cdata = comment_resp.json()
    assert cdata["is_verified_clinician"] is False
    assert cdata["parent_id"] is None
    assert cdata["author_display_name"] != ""


def test_threaded_comments_parent_id(social_on) -> None:
    community_id = _seed_community()
    author = _auth("user2@normal.clara")
    client.post("/api/v1/social/consent", headers=author)

    post = client.post(
        "/api/v1/social/posts",
        headers=author,
        json={
            "community_id": community_id,
            "title": "Hỏi về tập thể dục",
            "body": "Nên tập cardio hay nâng tạ trước?",
        },
    ).json()

    c1 = client.post(
        f"/api/v1/social/posts/{post['id']}/comments",
        headers=author,
        json={"body": "Nên khởi động kỹ trước đã."},
    ).json()
    assert c1["parent_id"] is None

    # Reply to c1
    c2 = client.post(
        f"/api/v1/social/posts/{post['id']}/comments",
        headers=author,
        json={"body": "Đồng ý, cardio nhẹ 5-10 phút.", "parent_id": c1["id"]},
    ).json()
    assert c2["parent_id"] == c1["id"]

    # Invalid parent_id should 404
    bad_reply = client.post(
        f"/api/v1/social/posts/{post['id']}/comments",
        headers=author,
        json={"body": "Sai parent_id", "parent_id": 999999},
    )
    assert bad_reply.status_code == 404

    # List comments includes parent_id
    clist = client.get(f"/api/v1/social/posts/{post['id']}/comments", headers=author).json()
    assert len(clist) >= 2
    c_map = {c["id"]: c for c in clist}
    assert c_map[c2["id"]]["parent_id"] == c1["id"]


def test_post_bookmark_toggle_and_listing(social_on) -> None:
    community_id = _seed_community()
    user = _auth("user3@normal.clara")
    client.post("/api/v1/social/consent", headers=user)

    post = client.post(
        "/api/v1/social/posts",
        headers=user,
        json={
            "community_id": community_id,
            "title": "Thực đơn mẫu 7 ngày",
            "body": "Chia sẻ thực đơn giảm cân an toàn.",
        },
    ).json()

    # Initial check: is_bookmarked False
    check1 = client.get(f"/api/v1/social/posts/{post['id']}", headers=user).json()
    assert check1["is_bookmarked"] is False

    # Toggle bookmark on
    b1 = client.post(f"/api/v1/social/posts/{post['id']}/bookmark", headers=user)
    assert b1.status_code == 200
    assert b1.json() == {"bookmarked": True}

    check2 = client.get(f"/api/v1/social/posts/{post['id']}", headers=user).json()
    assert check2["is_bookmarked"] is True

    # List bookmarks
    my_bms = client.get("/api/v1/social/me/bookmarks", headers=user)
    assert my_bms.status_code == 200
    bm_posts = my_bms.json()
    assert any(p["id"] == post["id"] for p in bm_posts)
    target_post = next(p for p in bm_posts if p["id"] == post["id"])
    assert target_post["is_bookmarked"] is True

    # Toggle bookmark off
    b2 = client.post(f"/api/v1/social/posts/{post['id']}/bookmark", headers=user)
    assert b2.status_code == 200
    assert b2.json() == {"bookmarked": False}

    check3 = client.get(f"/api/v1/social/posts/{post['id']}", headers=user).json()
    assert check3["is_bookmarked"] is False

    my_bms2 = client.get("/api/v1/social/me/bookmarks", headers=user).json()
    assert not any(p["id"] == post["id"] for p in my_bms2)


def test_post_search_with_and_without_community(social_on) -> None:
    c1_id = _seed_community("tim-mach", "Tim Mạch")
    c2_id = _seed_community("da-lieu", "Da Liễu")

    headers = _auth("user4@normal.clara")
    client.post("/api/v1/social/consent", headers=headers)

    p1 = client.post(
        "/api/v1/social/posts",
        headers=headers,
        json={
            "community_id": c1_id,
            "title": "Chỉ số huyết áp chuẩn",
            "body": "Cách đo huyết áp chính xác tại nhà bằng máy điện tử.",
        },
    ).json()

    p2 = client.post(
        "/api/v1/social/posts",
        headers=headers,
        json={
            "community_id": c2_id,
            "title": "Chăm sóc da khô",
            "body": "Dưỡng ẩm da mùa lạnh hiệu quả.",
        },
    ).json()

    # Search with query string matching p1
    res1 = client.get("/api/v1/social/posts/search?q=huyết áp", headers=headers)
    assert res1.status_code == 200
    ids1 = [p["id"] for p in res1.json()]
    assert p1["id"] in ids1
    assert p2["id"] not in ids1

    # Search with community filter
    res2 = client.get(f"/api/v1/social/posts/search?community_id={c1_id}", headers=headers)
    assert res2.status_code == 200
    ids2 = [p["id"] for p in res2.json()]
    assert p1["id"] in ids2
    assert p2["id"] not in ids2

    # Search matching body
    res3 = client.get("/api/v1/social/posts/search?q=mùa lạnh", headers=headers)
    assert res3.status_code == 200
    ids3 = [p["id"] for p in res3.json()]
    assert p2["id"] in ids3


def test_post_and_comment_deletion_rbac(social_on) -> None:
    community_id = _seed_community()
    author = _auth("user5@normal.clara")
    other_user = _auth("user6@normal.clara")
    client.post("/api/v1/social/consent", headers=author)
    client.post("/api/v1/social/consent", headers=other_user)

    post = client.post(
        "/api/v1/social/posts",
        headers=author,
        json={
            "community_id": community_id,
            "title": "Bài viết sắp xóa",
            "body": "Sẽ xóa bài này.",
        },
    ).json()

    comment = client.post(
        f"/api/v1/social/posts/{post['id']}/comments",
        headers=author,
        json={"body": "Bình luận sắp xóa."},
    ).json()

    # Non-author cannot delete comment
    c_del_forbidden = client.delete(f"/api/v1/social/comments/{comment['id']}", headers=other_user)
    assert c_del_forbidden.status_code == 403

    # Non-author cannot delete post
    p_del_forbidden = client.delete(f"/api/v1/social/posts/{post['id']}", headers=other_user)
    assert p_del_forbidden.status_code == 403

    # Author deletes comment
    c_del_ok = client.delete(f"/api/v1/social/comments/{comment['id']}", headers=author)
    assert c_del_ok.status_code == 200
    assert c_del_ok.json() == {"deleted": True}

    # Deleted comment no longer listed
    clist = client.get(f"/api/v1/social/posts/{post['id']}/comments", headers=author).json()
    assert not any(c["id"] == comment["id"] for c in clist)

    # Admin deletes post
    settings = get_settings()
    admin_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.auth_bootstrap_admin_email,
            "password": settings.auth_bootstrap_admin_password,
        },
    ).json()
    admin = {"Authorization": f"Bearer {admin_login['access_token']}"}

    p_del_admin = client.delete(f"/api/v1/social/posts/{post['id']}", headers=admin)
    assert p_del_admin.status_code == 200
    assert p_del_admin.json() == {"deleted": True}

    # Deleted post returns 404
    get_del_post = client.get(f"/api/v1/social/posts/{post['id']}", headers=author)
    assert get_del_post.status_code == 404


def test_leave_community(social_on) -> None:
    community_id = _seed_community("nhi-khoa", "Nhi Khoa")
    user = _auth("user7@normal.clara")
    client.post("/api/v1/social/consent", headers=user)

    # Join
    j_resp = client.post(f"/api/v1/social/communities/{community_id}/join", headers=user)
    assert j_resp.status_code == 200
    assert j_resp.json()["joined"] is True

    # Leave
    l_resp = client.post(f"/api/v1/social/communities/{community_id}/leave", headers=user)
    assert l_resp.status_code == 200
    assert l_resp.json()["joined"] is False

    # Check list communities
    comms = client.get("/api/v1/social/communities", headers=user).json()
    target_c = next(c for c in comms if c["id"] == community_id)
    assert target_c["joined"] is False


def test_reactions_breakdown_and_user_reaction(social_on) -> None:
    community_id = _seed_community()
    user_a = _auth("user_a@normal.clara")
    user_b = _auth("user_b@normal.clara")
    client.post("/api/v1/social/consent", headers=user_a)
    client.post("/api/v1/social/consent", headers=user_b)

    post = client.post(
        "/api/v1/social/posts",
        headers=user_a,
        json={
            "community_id": community_id,
            "title": "Phản hồi bài viết",
            "body": "Kiểm tra breakdown phản hồi.",
        },
    ).json()

    # User A reacts 'helpful'
    client.post(
        f"/api/v1/social/posts/{post['id']}/reactions",
        headers=user_a,
        json={"kind": "helpful"},
    )
    # User B reacts 'thanks'
    client.post(
        f"/api/v1/social/posts/{post['id']}/reactions",
        headers=user_b,
        json={"kind": "thanks"},
    )

    # Fetch post from user A perspective
    p_a = client.get(f"/api/v1/social/posts/{post['id']}", headers=user_a).json()
    assert p_a["reaction_count"] == 2
    assert p_a["user_reaction"] == "helpful"
    assert p_a["reactions_breakdown"] == {"helpful": 1, "thanks": 1}

    # Fetch post from user B perspective
    p_b = client.get(f"/api/v1/social/posts/{post['id']}", headers=user_b).json()
    assert p_b["reaction_count"] == 2
    assert p_b["user_reaction"] == "thanks"
    assert p_b["reactions_breakdown"] == {"helpful": 1, "thanks": 1}
