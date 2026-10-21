"""Focused tests for RBAC object-level profile scope and IDOR prevention.

Validates that:
1. Normal user resolves own profile (allow).
2. Normal user requesting another user's profile is denied with 404 scope_forbidden (IDOR blocked).
3. Admin user without break-glass workflow cannot bypass profile isolation (denied 404).
4. Whitespace and empty profile IDs gracefully fall back or fail safely without leak.
5. Family grant scope enforces action boundary (disallows ungranted action).
6. Family grant scope enforces data class boundary (disallows ungranted class).
7. Expired or revoked Family grant denies access immediately.
8. ProfileScope enforces owner role invariant (rejects profile.user_id != actor.id).
9. owner_profile_scope validates profile ownership before returning scope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clara_api.core.security import TokenPayload
from clara_api.db.base import Base
from clara_api.db.models import FamilyAccessGrant, PhrProfile, User
from clara_api.glhs.adapters import owner_profile_scope
from clara_api.lifemap.profile_scope import (
    ProfileScope,
    require_profile_scope,
    resolve_profile_scope,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _create_user_and_profile(
    db: Session, email_prefix: str, role: str = "normal"
) -> tuple[User, PhrProfile]:
    user = User(
        email=f"{email_prefix}-{uuid4().hex[:8]}@example.test",
        hashed_password="pbkdf2_sha256$test_dummy_hash",
        role=role,
        full_name=f"User {email_prefix}",
        status="active",
        is_email_verified=True,
    )
    db.add(user)
    db.flush()
    profile = PhrProfile(
        user_id=user.id,
        public_id=f"prof-{uuid4().hex[:12]}",
        status="active",
    )
    db.add(profile)
    db.flush()
    return user, profile


def test_user_resolves_own_profile_default(db_session: Session) -> None:
    user, profile = _create_user_and_profile(db_session, "user-a")
    token = TokenPayload(sub=user.email, role=user.role)

    scope = resolve_profile_scope(db_session, token)
    assert scope.is_owner is True
    assert scope.profile.id == profile.id
    assert scope.actor.id == user.id
    assert scope.actor_role == "owner"


def test_user_resolves_own_profile_explicit(db_session: Session) -> None:
    user, profile = _create_user_and_profile(db_session, "user-a")
    token = TokenPayload(sub=user.email, role=user.role)

    scope = resolve_profile_scope(db_session, token, requested_profile=profile.public_id)
    assert scope.is_owner is True
    assert scope.profile.id == profile.id


def test_idor_blocked_for_unauthorized_user(db_session: Session) -> None:
    user_a, profile_a = _create_user_and_profile(db_session, "user-a")
    user_b, profile_b = _create_user_and_profile(db_session, "user-b")
    token_b = TokenPayload(sub=user_b.email, role=user_b.role)

    with pytest.raises(HTTPException) as exc_info:
        resolve_profile_scope(db_session, token_b, requested_profile=profile_a.public_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "scope_forbidden", "message": "Profile not found"}


def test_admin_cannot_bypass_profile_scope_without_break_glass(db_session: Session) -> None:
    user_a, profile_a = _create_user_and_profile(db_session, "user-a")
    admin, _ = _create_user_and_profile(db_session, "admin", role="admin")
    token_admin = TokenPayload(sub=admin.email, role=admin.role)

    with pytest.raises(HTTPException) as exc_info:
        resolve_profile_scope(db_session, token_admin, requested_profile=profile_a.public_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "scope_forbidden", "message": "Profile not found"}


def test_whitespace_and_empty_profile_id_fallbacks(db_session: Session) -> None:
    user, profile = _create_user_and_profile(db_session, "user-a")
    token = TokenPayload(sub=user.email, role=user.role)

    scope = resolve_profile_scope(db_session, token, requested_profile="   ")
    assert scope.is_owner is True
    assert scope.profile.id == profile.id

    scope_req = require_profile_scope(db_session, user=user, profile_id="   ")
    assert scope_req.is_owner is True
    assert scope_req.profile.id == profile.id


def test_family_grant_allows_specified_action_and_data_class(db_session: Session) -> None:
    user_a, profile_a = _create_user_and_profile(db_session, "user-a")
    user_b, _ = _create_user_and_profile(db_session, "user-b")
    token_b = TokenPayload(sub=user_b.email, role=user_b.role)

    now = datetime.now(UTC)
    grant = FamilyAccessGrant(
        grantor_user_id=user_a.id,
        grantee_user_id=user_b.id,
        profile_id=profile_a.id,
        status="active",
        object_type="profile",
        object_id=profile_a.public_id,
        allowed_actions_json=["view"],
        data_classes_json=["lifemap"],
        purpose="self_care",
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=7),
    )
    db_session.add(grant)
    db_session.commit()

    scope = resolve_profile_scope(
        db_session,
        token_b,
        requested_profile=profile_a.public_id,
        action="view",
        data_class="lifemap",
    )
    assert scope.is_owner is False
    assert scope.actor_role == "caregiver"
    assert scope.grant_id == grant.id


def test_family_grant_denies_ungranted_action_or_class(db_session: Session) -> None:
    user_a, profile_a = _create_user_and_profile(db_session, "user-a")
    user_b, _ = _create_user_and_profile(db_session, "user-b")
    token_b = TokenPayload(sub=user_b.email, role=user_b.role)

    now = datetime.now(UTC)
    grant = FamilyAccessGrant(
        grantor_user_id=user_a.id,
        grantee_user_id=user_b.id,
        profile_id=profile_a.id,
        status="active",
        object_type="profile",
        object_id=profile_a.public_id,
        allowed_actions_json=["view"],
        data_classes_json=["lifemap"],
        purpose="self_care",
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=7),
    )
    db_session.add(grant)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_action:
        resolve_profile_scope(
            db_session,
            token_b,
            requested_profile=profile_a.public_id,
            action="create",
            data_class="lifemap",
        )
    assert exc_action.value.status_code == 404

    with pytest.raises(HTTPException) as exc_class:
        resolve_profile_scope(
            db_session,
            token_b,
            requested_profile=profile_a.public_id,
            action="view",
            data_class="medications",
        )
    assert exc_class.value.status_code == 404


def test_expired_or_revoked_grant_denies_access(db_session: Session) -> None:
    user_a, profile_a = _create_user_and_profile(db_session, "user-a")
    user_b, _ = _create_user_and_profile(db_session, "user-b")
    token_b = TokenPayload(sub=user_b.email, role=user_b.role)

    now = datetime.now(UTC)
    expired_grant = FamilyAccessGrant(
        grantor_user_id=user_a.id,
        grantee_user_id=user_b.id,
        profile_id=profile_a.id,
        status="active",
        object_type="profile",
        object_id=profile_a.public_id,
        allowed_actions_json=["view"],
        data_classes_json=["lifemap"],
        purpose="self_care",
        starts_at=now - timedelta(days=7),
        expires_at=now - timedelta(days=1),
    )
    db_session.add(expired_grant)
    db_session.commit()

    with pytest.raises(HTTPException):
        resolve_profile_scope(
            db_session,
            token_b,
            requested_profile=profile_a.public_id,
            action="view",
            data_class="lifemap",
        )


def test_profile_scope_enforces_owner_role_invariant() -> None:
    u1 = User(id=1, email="u1@test.com")
    p2 = PhrProfile(id=2, user_id=2, public_id="prof-2")

    with pytest.raises(ValueError, match="requires profile.user_id == actor.id"):
        ProfileScope(
            actor=u1,
            profile=p2,
            actor_role="owner",
            purpose="self_care",
            allowed_actions=frozenset({"view"}),
            allowed_data_classes=frozenset({"lifemap"}),
        )


def test_owner_profile_scope_rejects_cross_user_profile() -> None:
    u1 = User(id=1, email="u1@test.com")
    p2 = PhrProfile(id=2, user_id=2, public_id="prof-2")

    with pytest.raises(ValueError, match="owner_profile_scope requires profile.user_id"):
        owner_profile_scope(profile=p2, actor=u1)
