# ruff: noqa: E501
"""CLARA Health Social platform API (spec: .kiro/specs/clara-health-social).

A community/social layer for peer support around health topics, built additive
and behind the ``social_platform_enabled`` master flag (default OFF). When the
flag is off EVERY route in this router returns 404 so the baseline surface is
byte-identical to today.

Safety invariants (regression-locked, mirror the rest of CLARA):

* **PHR isolation** — no social route ever reads or writes PHR/medical-record
  data. The social profile is a separate, self-declared display object.
* **Consent gate** — writing (posting/commenting/reacting/joining) requires an
  active ``social_participation_v1`` consent grant, recorded in the shared
  ``UserConsent`` ledger.
* **Moderation gate** — every user-authored text body is screened by the ML
  ``/v1/social/moderate`` guard (legal hard-guard + emergency fast-path + PII
  filter) BEFORE it is persisted/published. A blocked body is never stored as
  visible content; an emergency escalates.
* **No vanity metrics** — reactions are recorded but public vanity counts are
  not emphasized; ranking never uses engagement-maximizing signals.
* **No-PII audit** — moderation/report actions log opaque references only.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    SocialComment,
    SocialCommunity,
    SocialMembership,
    SocialModerationAudit,
    SocialPost,
    SocialProfile,
    SocialReaction,
    SocialReport,
    User,
    UserConsent,
)
from clara_api.db.session import get_db

router = APIRouter()

SOCIAL_CONSENT_TYPE = "social_participation_v1"
_REACTION_KINDS = frozenset({"helpful", "relate", "thanks"})
_MAX_BODY = 5000
_MAX_TITLE = 200


# --------------------------------------------------------------------------
# Flag gate
# --------------------------------------------------------------------------
def _require_social_enabled() -> None:
    """404 when the social master flag is off (baseline unchanged, spec R1/R12)."""
    if not get_settings().social_platform_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _require_user(token: TokenPayload, db: Session) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Không tìm thấy người dùng"
        )
    return user


def _opaque_ref(user_id: int) -> str:
    """Stable, non-reversible reference for PII-free audit rows."""
    return hashlib.sha256(f"clara-social:{user_id}".encode()).hexdigest()[:32]


# --------------------------------------------------------------------------
# Consent
# --------------------------------------------------------------------------
def _has_social_consent(db: Session, *, user_id: int) -> bool:
    latest = db.execute(
        select(UserConsent)
        .where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == SOCIAL_CONSENT_TYPE,
        )
        .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
    ).scalar_one_or_none()
    return bool(latest and latest.revoked_at is None)


def _require_social_consent(db: Session, *, user_id: int) -> None:
    if not _has_social_consent(db, user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=(
                "Bạn cần đồng ý tham gia cộng đồng CLARA "
                "(quy tắc ứng xử & quyền riêng tư) trước khi đăng nội dung."
            ),
        )


# --------------------------------------------------------------------------
# Moderation gate (ML bridge, fail-closed)
# --------------------------------------------------------------------------
def _moderate_text(body: str) -> dict[str, Any]:
    """Screen user text via the ML social-moderation guard.

    Returns a verdict dict ``{action, reason, emergency}``. Fails CLOSED: if the
    ML guard is unreachable, the text is treated as blocked rather than silently
    published, because the moderation gate is a safety invariant.
    """
    settings = get_settings()
    text = (body or "").strip()
    if not text:
        return {"action": "block", "reason": "empty", "emergency": False}

    ml_base = settings.ml_service_url.rstrip("/") if hasattr(settings, "ml_service_url") else ""
    if not ml_base:
        # No ML configured: allow in dev, block in production (fail-closed).
        if settings.environment.lower() == "production":
            return {"action": "block", "reason": "moderation_unavailable", "emergency": False}
        return {"action": "allow", "reason": "dev_no_ml", "emergency": False}

    try:
        import httpx

        headers: dict[str, str] = {}
        key = getattr(settings, "ml_internal_api_key", "").strip()
        if key:
            headers["X-ML-Internal-Key"] = key
        resp = httpx.post(
            f"{ml_base}/v1/social/moderate",
            json={"text": text},
            headers=headers,
            timeout=getattr(settings, "ml_service_timeout_seconds", 30.0),
        )
        resp.raise_for_status()
        data = resp.json()
        action = str(data.get("action", "block")).lower()
        if action not in {"allow", "warn", "block", "escalate"}:
            action = "block"
        return {
            "action": action,
            "reason": str(data.get("reason", "")),
            "emergency": bool(data.get("emergency", False)),
        }
    except Exception:
        # Fail-closed: never publish unscreened content on a guard failure.
        return {"action": "block", "reason": "moderation_error", "emergency": False}


def _enforce_moderation(db: Session, *, user_id: int, body: str, surface: str) -> None:
    """Apply the moderation verdict; block/escalate raise, allow/warn pass.

    Records a PII-free audit row for any non-allow verdict. ``surface`` is the
    target type (``post``/``comment``) for the audit row.
    """
    verdict = _moderate_text(body)
    action = verdict["action"]
    if action in {"block", "escalate"} or verdict["emergency"]:
        _record_moderation_audit(
            db,
            user_id=user_id,
            action=action,
            target_type=surface,
            reason=verdict.get("reason", ""),
        )
        if verdict["emergency"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Nội dung có dấu hiệu khẩn cấp y tế. Nếu bạn hoặc người khác "
                    "đang gặp nguy hiểm, hãy gọi cấp cứu 115 ngay. CLARA không xử lý "
                    "tình huống cấp cứu qua cộng đồng."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Nội dung không phù hợp quy tắc cộng đồng (không kê đơn/chẩn đoán/"
                "liều dùng cá nhân). Vui lòng chỉnh sửa và thử lại."
            ),
        )


def _record_moderation_audit(
    db: Session,
    *,
    user_id: int,
    action: str,
    target_type: str,
    target_id: int = 0,
    reason: str = "",
) -> None:
    db.add(
        SocialModerationAudit(
            actor_ref=_opaque_ref(user_id),
            action=action[:32],
            target_type=target_type[:16],
            target_id=target_id,
            reason=reason[:64],
        )
    )
    db.flush()


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class ConsentStatusResponse(BaseModel):
    consent_type: str = SOCIAL_CONSENT_TYPE
    granted: bool


class ProfileResponse(BaseModel):
    handle: str
    display_name: str
    bio: str
    role_badge: str


class ProfileUpdate(BaseModel):
    display_name: str = Field(default="", max_length=80)
    bio: str = Field(default="", max_length=280)


class CommunityResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    member_count: int
    joined: bool


class PostCreate(BaseModel):
    community_id: int
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    body: str = Field(min_length=1, max_length=_MAX_BODY)


class PostResponse(BaseModel):
    id: int
    community_id: int
    author_handle: str
    title: str
    body: str
    created_at: str
    comment_count: int
    reaction_count: int


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=_MAX_BODY)


class CommentResponse(BaseModel):
    id: int
    post_id: int
    author_handle: str
    body: str
    created_at: str


class ReactionRequest(BaseModel):
    kind: str = Field(description="helpful | relate | thanks")


class ReportRequest(BaseModel):
    target_type: str = Field(description="post | comment")
    target_id: int
    reason: str = Field(default="", max_length=280)


class ModerationActionRequest(BaseModel):
    # "dismiss" keeps the content and closes the report; "remove" soft-deletes
    # the target (post/comment) and closes the report.
    action: str = Field(description="dismiss | remove")


# --------------------------------------------------------------------------
# Profile helpers
# --------------------------------------------------------------------------
def _get_or_create_profile(db: Session, user: User) -> SocialProfile:
    profile = db.execute(
        select(SocialProfile).where(SocialProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        base_handle = f"clara{user.id}"
        profile = SocialProfile(
            user_id=user.id,
            handle=base_handle,
            display_name=(user.full_name or base_handle)[:80],
            bio="",
            role_badge=user.role if user.role in {"doctor", "researcher"} else "",
        )
        db.add(profile)
        db.flush()
    return profile


def _profile_out(p: SocialProfile) -> ProfileResponse:
    return ProfileResponse(
        handle=p.handle,
        display_name=p.display_name,
        bio=p.bio,
        role_badge=p.role_badge or "",
    )


def _handle_for(db: Session, user_id: int) -> str:
    p = db.execute(
        select(SocialProfile).where(SocialProfile.user_id == user_id)
    ).scalar_one_or_none()
    return p.handle if p else f"clara{user_id}"


# --------------------------------------------------------------------------
# Consent routes
# --------------------------------------------------------------------------
@router.get("/consent", response_model=ConsentStatusResponse)
def get_social_consent(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> ConsentStatusResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    return ConsentStatusResponse(granted=_has_social_consent(db, user_id=user.id))


@router.post("/consent", response_model=ConsentStatusResponse)
def grant_social_consent(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> ConsentStatusResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    if not _has_social_consent(db, user_id=user.id):
        db.add(
            UserConsent(
                user_id=user.id,
                consent_type=SOCIAL_CONSENT_TYPE,
                consent_version="2026-05-v1",
            )
        )
        db.commit()
    return ConsentStatusResponse(granted=True)


@router.delete("/consent", response_model=ConsentStatusResponse)
def revoke_social_consent(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> ConsentStatusResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    db.add(
        UserConsent(
            user_id=user.id,
            consent_type=SOCIAL_CONSENT_TYPE,
            consent_version="2026-05-v1",
            revoked_at=datetime.now(UTC),
        )
    )
    db.commit()
    return ConsentStatusResponse(granted=False)


# --------------------------------------------------------------------------
# Profile routes
# --------------------------------------------------------------------------
@router.get("/me/profile", response_model=ProfileResponse)
def get_my_profile(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    profile = _get_or_create_profile(db, user)
    db.commit()
    return _profile_out(profile)


@router.patch("/me/profile", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    profile = _get_or_create_profile(db, user)
    if payload.display_name.strip():
        profile.display_name = payload.display_name.strip()[:80]
    profile.bio = payload.bio.strip()[:280]
    db.add(profile)
    db.commit()
    return _profile_out(profile)


@router.get("/profiles/{handle}", response_model=ProfileResponse)
def get_profile(
    handle: str,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    _require_social_enabled()
    _require_user(token, db)
    profile = db.execute(
        select(SocialProfile).where(SocialProfile.handle == handle)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ")
    return _profile_out(profile)


# --------------------------------------------------------------------------
# Communities
# --------------------------------------------------------------------------
def _member_count(db: Session, community_id: int) -> int:
    return int(
        db.execute(
            select(func.count(SocialMembership.id)).where(
                SocialMembership.community_id == community_id
            )
        ).scalar_one()
    )


@router.get("/communities", response_model=list[CommunityResponse])
def list_communities(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> list[CommunityResponse]:
    _require_social_enabled()
    user = _require_user(token, db)
    communities = (
        db.execute(
            select(SocialCommunity)
            .where(SocialCommunity.is_curated.is_(True))
            .order_by(SocialCommunity.name.asc())
        )
        .scalars()
        .all()
    )
    joined_ids = set(
        db.execute(
            select(SocialMembership.community_id).where(SocialMembership.user_id == user.id)
        )
        .scalars()
        .all()
    )
    return [
        CommunityResponse(
            id=c.id,
            slug=c.slug,
            name=c.name,
            description=c.description,
            member_count=_member_count(db, c.id),
            joined=c.id in joined_ids,
        )
        for c in communities
    ]


@router.post("/communities/{community_id}/join", response_model=CommunityResponse)
def join_community(
    community_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CommunityResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    _require_social_consent(db, user_id=user.id)
    community = db.get(SocialCommunity, community_id)
    if community is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cộng đồng")
    existing = db.execute(
        select(SocialMembership).where(
            SocialMembership.community_id == community_id,
            SocialMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(SocialMembership(community_id=community_id, user_id=user.id))
        db.commit()
    return CommunityResponse(
        id=community.id,
        slug=community.slug,
        name=community.name,
        description=community.description,
        member_count=_member_count(db, community.id),
        joined=True,
    )


@router.post("/communities/{community_id}/leave", response_model=CommunityResponse)
def leave_community(
    community_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CommunityResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    community = db.get(SocialCommunity, community_id)
    if community is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cộng đồng")
    existing = db.execute(
        select(SocialMembership).where(
            SocialMembership.community_id == community_id,
            SocialMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()
    return CommunityResponse(
        id=community.id,
        slug=community.slug,
        name=community.name,
        description=community.description,
        member_count=_member_count(db, community.id),
        joined=False,
    )


# --------------------------------------------------------------------------
# Posts / comments / reactions
# --------------------------------------------------------------------------
def _post_out(db: Session, post: SocialPost) -> PostResponse:
    comment_count = int(
        db.execute(
            select(func.count(SocialComment.id)).where(
                SocialComment.post_id == post.id, SocialComment.is_deleted.is_(False)
            )
        ).scalar_one()
    )
    reaction_count = int(
        db.execute(
            select(func.count(SocialReaction.id)).where(SocialReaction.post_id == post.id)
        ).scalar_one()
    )
    return PostResponse(
        id=post.id,
        community_id=post.community_id,
        author_handle=_handle_for(db, post.author_id),
        title=post.title,
        body=post.body,
        created_at=post.created_at.isoformat() if post.created_at else "",
        comment_count=comment_count,
        reaction_count=reaction_count,
    )


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> PostResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    _require_social_consent(db, user_id=user.id)
    community = db.get(SocialCommunity, payload.community_id)
    if community is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cộng đồng")
    # Pre-publish moderation on BOTH title and body (safety invariant).
    _enforce_moderation(db, user_id=user.id, body=f"{payload.title}\n{payload.body}", surface="post")
    post = SocialPost(
        community_id=payload.community_id,
        author_id=user.id,
        title=payload.title.strip()[:_MAX_TITLE],
        body=payload.body.strip()[:_MAX_BODY],
    )
    db.add(post)
    db.commit()
    return _post_out(db, post)


@router.get("/posts/{post_id}", response_model=PostResponse)
def get_post(
    post_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> PostResponse:
    _require_social_enabled()
    _require_user(token, db)
    post = db.get(SocialPost, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
    return _post_out(db, post)


@router.delete("/posts/{post_id}", response_model=dict[str, bool])
def delete_post(
    post_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _require_social_enabled()
    user = _require_user(token, db)
    post = db.get(SocialPost, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
    if post.author_id != user.id and token.role != "admin" and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không đủ quyền")
    post.is_deleted = True
    db.add(post)
    db.commit()
    return {"deleted": True}


@router.get("/communities/{community_id}/posts", response_model=list[PostResponse])
def list_community_posts(
    community_id: int,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> list[PostResponse]:
    _require_social_enabled()
    _require_user(token, db)
    posts = (
        db.execute(
            select(SocialPost)
            .where(SocialPost.community_id == community_id, SocialPost.is_deleted.is_(False))
            .order_by(SocialPost.created_at.desc(), SocialPost.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return [_post_out(db, p) for p in posts]


@router.get("/feed", response_model=list[PostResponse])
def get_feed(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> list[PostResponse]:
    """Recency-ranked feed. Personalized to joined communities when the user has
    joined any; otherwise a curated global recency feed. No engagement-maximizing
    signals are used in ranking (spec R9/R11)."""
    _require_social_enabled()
    user = _require_user(token, db)
    joined_ids = list(
        db.execute(
            select(SocialMembership.community_id).where(SocialMembership.user_id == user.id)
        )
        .scalars()
        .all()
    )
    stmt = select(SocialPost).where(SocialPost.is_deleted.is_(False))
    if joined_ids:
        stmt = stmt.where(SocialPost.community_id.in_(joined_ids))
    stmt = stmt.order_by(SocialPost.created_at.desc(), SocialPost.id.desc()).limit(limit).offset(offset)
    posts = db.execute(stmt).scalars().all()
    return [_post_out(db, p) for p in posts]


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: int,
    payload: CommentCreate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CommentResponse:
    _require_social_enabled()
    user = _require_user(token, db)
    _require_social_consent(db, user_id=user.id)
    post = db.get(SocialPost, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
    _enforce_moderation(db, user_id=user.id, body=payload.body, surface="comment")
    comment = SocialComment(
        post_id=post_id,
        author_id=user.id,
        body=payload.body.strip()[:_MAX_BODY],
    )
    db.add(comment)
    db.commit()
    return CommentResponse(
        id=comment.id,
        post_id=post_id,
        author_handle=_handle_for(db, user.id),
        body=comment.body,
        created_at=comment.created_at.isoformat() if comment.created_at else "",
    )


@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
def list_comments(
    post_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> list[CommentResponse]:
    _require_social_enabled()
    _require_user(token, db)
    comments = (
        db.execute(
            select(SocialComment)
            .where(SocialComment.post_id == post_id, SocialComment.is_deleted.is_(False))
            .order_by(SocialComment.created_at.asc(), SocialComment.id.asc())
        )
        .scalars()
        .all()
    )
    return [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            author_handle=_handle_for(db, c.author_id),
            body=c.body,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in comments
    ]


@router.post("/posts/{post_id}/reactions", response_model=dict[str, Any])
def react_to_post(
    post_id: int,
    payload: ReactionRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_social_enabled()
    user = _require_user(token, db)
    _require_social_consent(db, user_id=user.id)
    kind = payload.kind.strip().lower()
    if kind not in _REACTION_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại phản hồi không hợp lệ")
    post = db.get(SocialPost, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
    existing = db.execute(
        select(SocialReaction).where(
            SocialReaction.post_id == post_id, SocialReaction.user_id == user.id
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(SocialReaction(post_id=post_id, user_id=user.id, kind=kind))
    elif existing.kind == kind:
        db.delete(existing)  # toggle off
    else:
        existing.kind = kind
        db.add(existing)
    db.commit()
    return {"ok": True}


@router.post("/reports", response_model=dict[str, bool], status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _require_social_enabled()
    user = _require_user(token, db)
    target_type = payload.target_type.strip().lower()
    if target_type not in {"post", "comment"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại báo cáo không hợp lệ")
    db.add(
        SocialReport(
            reporter_id=user.id,
            target_type=target_type,
            target_id=payload.target_id,
            reason=payload.reason.strip()[:32] or "other",
            detail=payload.reason.strip()[:500],
        )
    )
    db.commit()
    return {"reported": True}


# --------------------------------------------------------------------------
# Moderation queue (role-gated)
# --------------------------------------------------------------------------
@router.get("/moderation/reports", response_model=list[dict[str, Any]])
def list_reports(
    token: TokenPayload = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    _require_social_enabled()
    _require_user(token, db)
    reports = (
        db.execute(
            select(SocialReport)
            .where(SocialReport.status == "open")
            .order_by(SocialReport.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in reports
    ]


@router.post("/moderation/reports/{report_id}/action", response_model=dict[str, Any])
def act_on_report(
    report_id: int,
    payload: ModerationActionRequest,
    token: TokenPayload = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Resolve an open report (admin only).

    ``dismiss`` closes the report leaving content intact. ``remove`` soft-deletes
    the reported post/comment (sets ``is_deleted``/``moderation_status``) so it
    leaves feeds immediately, then closes the report. Every action writes a
    PII-free moderation-audit row (opaque actor ref, reason code only).
    """
    _require_social_enabled()
    admin = _require_user(token, db)
    action = payload.action.strip().lower()
    if action not in {"dismiss", "remove"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="H\u00e0nh \u0111\u1ed9ng kh\u00f4ng h\u1ee3p l\u1ec7"
        )
    report = db.get(SocialReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e1o c\u00e1o")

    if action == "remove":
        if report.target_type == "post":
            post = db.get(SocialPost, report.target_id)
            if post is not None:
                post.is_deleted = True
                post.moderation_status = "removed"
                db.add(post)
        elif report.target_type == "comment":
            comment = db.get(SocialComment, report.target_id)
            if comment is not None:
                comment.is_deleted = True
                comment.moderation_status = "removed"
                db.add(comment)

    report.status = "resolved"
    report.resolved_at = datetime.now(UTC)
    db.add(report)
    _record_moderation_audit(
        db,
        user_id=admin.id,
        action=f"report_{action}",
        target_type=report.target_type,
        target_id=report.target_id,
        reason=report.reason or "",
    )
    db.commit()
    return {"id": report.id, "status": report.status, "action": action}
