"""Phase-3 Visit APIs. Router registration intentionally lives in api/router.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import LifeMapVisit, PhrProfile
from clara_api.db.session import get_db
from clara_api.lifemap.visit_family_service import (
    DomainNotFoundError,
    DomainValidationError,
    add_visit_concern,
    approve_visit_pack,
    create_visit,
    create_visit_pack,
    create_visit_share,
    grant_visit_consent,
    link_visit_episode,
    resolve_visit_share,
    revoke_visit_consent,
    revoke_visit_share,
)

router = APIRouter()
pack_router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class VisitCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    goal: str = Field(default="", max_length=4000)
    visit_type: str = Field(default="other", max_length=64)
    scheduled_at: datetime | None = None


class ConcernRequest(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
    priority: str = "routine"


class EpisodeLinkRequest(BaseModel):
    episode_id: int = Field(gt=0)


class VisitPackRequest(BaseModel):
    selection: dict[str, Any]


class VisitShareRequest(BaseModel):
    expires_at: datetime


class VisitConsentRequest(BaseModel):
    purpose: str
    policy_version: str = Field(min_length=1, max_length=64)


def _raise(error: Exception) -> None:
    if isinstance(error, DomainNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, DomainValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


def _scope(db: Session, token: TokenPayload) -> tuple[object, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


def _visit_view(visit: LifeMapVisit) -> dict[str, Any]:
    return {
        "id": str(visit.id),
        "title": visit.title,
        "goal": visit.goal,
        "visit_type": visit.visit_type,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_visit_endpoint(
    payload: VisitCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        visit = create_visit(
            db,
            owner=user,
            profile_id=profile.id,
            title=payload.title,
            goal=payload.goal,
            visit_type=payload.visit_type,
            scheduled_at=payload.scheduled_at,
        )
        db.commit()
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)
    return _visit_view(visit)


@router.get("")
def list_visits(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    _, profile = _scope(db, token)
    return [
        _visit_view(row)
        for row in db.execute(
            select(LifeMapVisit)
            .where(LifeMapVisit.profile_id == profile.id)
            .order_by(LifeMapVisit.scheduled_at.desc(), LifeMapVisit.id.desc())
        ).scalars()
    ]


@router.get("/{visit_id}")
def get_visit(
    visit_id: int, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    from clara_api.lifemap.visit_family_service import (
        _owned_visit,  # local: API never bypasses scope
    )

    try:
        return _visit_view(_owned_visit(db, owner=user, visit_id=visit_id))
    except DomainNotFoundError as error:
        _raise(error)


@router.post("/{visit_id}/concerns", status_code=status.HTTP_201_CREATED)
def add_concern_endpoint(
    visit_id: int,
    payload: ConcernRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        concern = add_visit_concern(
            db, owner=user, visit_id=visit_id, text=payload.text, priority=payload.priority
        )
        db.commit()
        return {"id": str(concern.id), "priority": concern.priority}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/episodes", status_code=status.HTTP_201_CREATED)
def link_episode_endpoint(
    visit_id: int,
    payload: EpisodeLinkRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        link = link_visit_episode(db, owner=user, visit_id=visit_id, episode_id=payload.episode_id)
        db.commit()
        return {"id": str(link.id), "episode_id": str(link.episode_id)}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/pack", status_code=status.HTTP_201_CREATED)
def create_pack_endpoint(
    visit_id: int,
    payload: VisitPackRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        pack = create_visit_pack(db, owner=user, visit_id=visit_id, selection=payload.selection)
        db.commit()
        return {"id": str(pack.id), "version_no": pack.version_no, "status": pack.status}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.post("/{pack_id}/approve")
def approve_pack_endpoint(
    pack_id: int, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        pack = approve_visit_pack(db, owner=user, pack_id=pack_id)
        db.commit()
        return {"id": str(pack.id), "version_no": pack.version_no, "status": pack.status}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.post("/{pack_id}/shares", status_code=status.HTTP_201_CREATED)
def create_share_endpoint(
    pack_id: int,
    payload: VisitShareRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        share, token_value = create_visit_share(
            db, owner=user, pack_id=pack_id, expires_at=payload.expires_at
        )
        db.commit()
        # Capability appears only at creation; database retains only its hash.
        return {"id": str(share.id), "token": token_value, "expires_at": share.expires_at}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.delete("/{pack_id}/shares/{share_id}")
def revoke_share_endpoint(
    pack_id: int,
    share_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        revoke_visit_share(db, owner=user, pack_id=pack_id, share_id=share_id)
        db.commit()
        return {"status": "revoked"}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/scribe-consents", status_code=status.HTTP_201_CREATED)
def grant_scribe_consent_endpoint(
    visit_id: int,
    payload: VisitConsentRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        consent = grant_visit_consent(
            db,
            owner=user,
            visit_id=visit_id,
            purpose=payload.purpose,
            policy_version=payload.policy_version,
        )
        db.commit()
        return {"id": str(consent.id), "purpose": consent.purpose, "status": "granted"}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.delete("/{visit_id}/scribe-consents/{purpose}")
def revoke_scribe_consent_endpoint(
    visit_id: int,
    purpose: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, int]:
    user, _ = _scope(db, token)
    try:
        count = revoke_visit_consent(db, owner=user, visit_id=visit_id, purpose=purpose)
        db.commit()
        return {"revoked": count}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@pack_router.get("/shared/{share_token}")
def view_shared_pack(share_token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        # Return the immutable approved snapshot, never a live profile projection.
        return resolve_visit_share(db, raw_token=share_token).contents_json
    except DomainNotFoundError as error:
        _raise(error)
