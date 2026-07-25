"""Phase-4 Family Circle APIs. All protected work delegates to live grant checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import FamilyAccessGrant, PhrProfile
from clara_api.db.session import get_db
from clara_api.lifemap.visit_family_service import (
    DomainAuthorizationError,
    DomainNotFoundError,
    DomainValidationError,
    accept_family_invitation,
    complete_delegated_task,
    create_family_invitation,
    list_family_access_log,
    record_caregiver_observation,
    revoke_family_access_grant,
)

router = APIRouter()
task_router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class InvitationRequest(BaseModel):
    recipient_email: str = Field(min_length=3, max_length=255)
    scope: dict[str, Any]
    purpose: str
    expires_at: datetime


class ObservationRequest(BaseModel):
    episode_id: int = Field(gt=0)
    purpose: str
    text: str = Field(min_length=2, max_length=4000)


class DelegationRequest(BaseModel):
    recipient_email: str = Field(min_length=3, max_length=255)
    purpose: str
    expires_at: datetime


class CompleteTaskRequest(BaseModel):
    purpose: str
    evidence: dict[str, Any] = Field(default_factory=dict)


def _raise(error: Exception) -> None:
    if isinstance(error, DomainNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, DomainAuthorizationError):
        raise HTTPException(status_code=403, detail="Family access is not authorized") from error
    if isinstance(error, DomainValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


def _profile(db: Session, token: TokenPayload) -> tuple[object, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    payload: InvitationRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    owner, profile = _profile(db, token)
    try:
        invitation, raw_token = create_family_invitation(
            db,
            owner=owner,
            profile_id=profile.id,
            recipient_email=payload.recipient_email,
            scope=payload.scope,
            purpose=payload.purpose,
            expires_at=payload.expires_at,
        )
        db.commit()
        # Delivery is explicitly out-of-band; CLARA does not pretend to have sent it.
        return {"id": str(invitation.id), "token": raw_token, "expires_at": invitation.expires_at}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/invitations/{invitation_token}/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(
    invitation_token: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    recipient = current_user(db, token)
    try:
        grant = accept_family_invitation(db, recipient=recipient, raw_token=invitation_token)
        db.commit()
        return {
            "id": str(grant.id),
            "profile_id": str(grant.profile_id),
            "object_type": grant.object_type,
            "object_id": grant.object_id,
            "allowed_actions": grant.allowed_actions_json,
            "purpose": grant.purpose,
            "expires_at": grant.expires_at,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.get("/relationships")
def relationships(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    user = current_user(db, token)
    now = datetime.now(UTC)
    grants = db.execute(
        select(FamilyAccessGrant)
        .where(
            FamilyAccessGrant.grantee_user_id == user.id,
            FamilyAccessGrant.status == "active",
            FamilyAccessGrant.revoked_at.is_(None),
            FamilyAccessGrant.expires_at > now,
        )
        .order_by(FamilyAccessGrant.id.desc())
    ).scalars()
    return [
        {
            "id": str(grant.id),
            "profile_id": str(grant.profile_id),
            "object_type": grant.object_type,
            "object_id": grant.object_id,
            "allowed_actions": grant.allowed_actions_json,
            "purpose": grant.purpose,
            "expires_at": grant.expires_at,
        }
        for grant in grants
    ]


@router.get("/access-grants")
def list_owner_grants(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    owner, profile = _profile(db, token)
    return [
        {
            "id": str(grant.id),
            "grantee_user_id": str(grant.grantee_user_id),
            "object_type": grant.object_type,
            "object_id": grant.object_id,
            "allowed_actions": grant.allowed_actions_json,
            "purpose": grant.purpose,
            "status": grant.status,
            "expires_at": grant.expires_at,
            "grant_version": grant.grant_version,
        }
        for grant in db.execute(
            select(FamilyAccessGrant)
            .where(
                FamilyAccessGrant.grantor_user_id == owner.id,
                FamilyAccessGrant.profile_id == profile.id,
            )
            .order_by(FamilyAccessGrant.id.desc())
        ).scalars()
    ]


@router.delete("/access-grants/{grant_id}")
def revoke_grant(
    grant_id: int, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    owner = current_user(db, token)
    try:
        grant = revoke_family_access_grant(db, owner=owner, grant_id=grant_id)
        db.commit()
        return {"id": str(grant.id), "status": grant.status, "grant_version": grant.grant_version}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@router.get("/access-log")
def access_log(db: Session = Depends(get_db), token: TokenPayload = USER) -> list[dict[str, Any]]:
    owner, profile = _profile(db, token)
    try:
        return [
            {
                "id": str(row.id),
                "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                "grant_id": str(row.grant_id) if row.grant_id else None,
                "object_type": row.object_type,
                "object_id": row.object_id,
                "action": row.action,
                "outcome": row.outcome,
                "purpose": row.purpose,
                "created_at": row.created_at,
            }
            for row in list_family_access_log(db, owner=owner, profile_id=profile.id)
        ]
    except DomainNotFoundError as error:
        _raise(error)


@router.post("/profiles/{profile_id}/caregiver-observations", status_code=status.HTTP_201_CREATED)
def caregiver_observation(
    profile_id: int,
    payload: ObservationRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    caregiver = current_user(db, token)
    try:
        event = record_caregiver_observation(
            db,
            caregiver=caregiver,
            profile_id=profile_id,
            episode_id=payload.episode_id,
            purpose=payload.purpose,
            text=payload.text,
        )
        db.commit()
        return {"id": str(event.id), "truth_state": event.truth_state, "source": event.source_kind}
    except (DomainAuthorizationError, DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/profiles/{profile_id}/care-tasks/{task_id}/complete")
def complete_task_as_caregiver(
    profile_id: int,
    task_id: int,
    payload: CompleteTaskRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    caregiver = current_user(db, token)
    try:
        task = complete_delegated_task(
            db,
            caregiver=caregiver,
            profile_id=profile_id,
            task_id=task_id,
            purpose=payload.purpose,
            evidence=payload.evidence,
        )
        db.commit()
        return {"id": str(task.id), "status": task.status, "completed_at": task.completed_at}
    except (DomainAuthorizationError, DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@task_router.post("/{task_id}/delegations", status_code=status.HTTP_201_CREATED)
def delegate_task(
    task_id: int,
    payload: DelegationRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    owner, profile = _profile(db, token)
    try:
        invitation, raw_token = create_family_invitation(
            db,
            owner=owner,
            profile_id=profile.id,
            recipient_email=payload.recipient_email,
            scope={
                "object_type": "care_task",
                "object_id": task_id,
                "allowed_actions": ["view", "complete_task"],
            },
            purpose=payload.purpose,
            expires_at=payload.expires_at,
        )
        db.commit()
        return {"id": str(invitation.id), "token": raw_token, "expires_at": invitation.expires_at}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)
