"""Phase-4 Family Circle APIs. All protected work delegates to live grant checks."""

from __future__ import annotations

import hmac
import json
import math
from datetime import UTC, datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    FamilyAccessGrant,
    FamilyAccessLog,
    LifeMapCareTask,
    LifeMapEpisode,
    LifeMapVisit,
    PhrProfile,
    User,
)
from clara_api.db.session import get_db
from clara_api.lifemap.visit_family_service import (
    DomainAuthorizationError,
    DomainNotFoundError,
    DomainValidationError,
    accept_family_invitation,
    acknowledge_care_task_notification,
    complete_delegated_task,
    create_family_grant_renewal,
    create_family_invitation,
    list_family_access_log,
    preview_family_invitation,
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
    episode_id: str = Field(min_length=1, max_length=64)
    purpose: str
    text: str = Field(min_length=2, max_length=4000)


class DelegationRequest(BaseModel):
    recipient_email: str = Field(min_length=3, max_length=255)
    purpose: str
    expires_at: datetime


class CompleteTaskRequest(BaseModel):
    purpose: str = Field(min_length=2, max_length=64)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence")
    @classmethod
    def evidence_is_bounded_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_bounded_evidence(value)
        _bounded_evidence_bytes(value)
        return value


class InvitationAcceptRequest(BaseModel):
    """Capability supplied out of the URL so it does not enter route logs."""

    token: str = Field(min_length=32, max_length=512)


def _invitation_capability(
    payload: InvitationAcceptRequest | None,
    x_family_invitation_token: str | None,
) -> str:
    """Read a one-time invitation capability without accepting URL input."""

    body_token = payload.token if payload is not None else None
    header_token = x_family_invitation_token.strip() if x_family_invitation_token else None
    if body_token and header_token and not hmac.compare_digest(body_token, header_token):
        raise HTTPException(status_code=422, detail="Invitation capability inputs do not match")
    raw_token = header_token or body_token
    if not raw_token:
        raise HTTPException(status_code=422, detail="Invitation capability is required")
    return raw_token


class NotificationAcknowledgementRequest(BaseModel):
    purpose: str = Field(min_length=2, max_length=64)


class GrantRenewalRequest(BaseModel):
    expires_at: datetime


MAX_EVIDENCE_BYTES = 16_000
MAX_EVIDENCE_DEPTH = 4
MAX_EVIDENCE_COLLECTION_ITEMS = 50
MAX_EVIDENCE_STRING_CHARS = 2_000
MAX_EVIDENCE_KEY_CHARS = 128


def _validate_bounded_evidence(value: Any, *, depth: int = 0) -> None:
    """Keep caregiver attestation evidence useful without accepting a record dump."""

    if depth > MAX_EVIDENCE_DEPTH:
        raise ValueError("Evidence is too deeply nested")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Evidence numbers must be finite")
        return
    if isinstance(value, str):
        if len(value) > MAX_EVIDENCE_STRING_CHARS:
            raise ValueError("Evidence text is too long")
        return
    if isinstance(value, list):
        if len(value) > MAX_EVIDENCE_COLLECTION_ITEMS:
            raise ValueError("Evidence contains too many items")
        for item in value:
            _validate_bounded_evidence(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_EVIDENCE_COLLECTION_ITEMS:
            raise ValueError("Evidence contains too many fields")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > MAX_EVIDENCE_KEY_CHARS:
                raise ValueError("Evidence field names are invalid")
            _validate_bounded_evidence(item, depth=depth + 1)
        return
    raise ValueError("Evidence contains an unsupported value")


def _bounded_evidence_bytes(value: dict[str, Any]) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("Evidence must be JSON serializable") from error
    if len(encoded) > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence is too large")


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, DomainNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, DomainAuthorizationError):
        raise HTTPException(status_code=403, detail="Family access is not authorized") from error
    if isinstance(error, DomainValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


def _profile(db: Session, token: TokenPayload) -> tuple[User, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


def _public_selector(model: Any, value: str):
    selector = model.public_id == value
    if value.isdecimal():
        selector = selector | (model.id == int(value))
    return selector


def _resolve_owned_grant_id(
    db: Session,
    *,
    reference: str,
    owner_id: int | None = None,
    grantee_id: int | None = None,
) -> int:
    conditions = [_public_selector(FamilyAccessGrant, reference)]
    if owner_id is not None:
        conditions.append(FamilyAccessGrant.grantor_user_id == owner_id)
    if grantee_id is not None:
        conditions.append(FamilyAccessGrant.grantee_user_id == grantee_id)
    resolved = db.execute(
        select(FamilyAccessGrant.id).where(*conditions)
    ).scalar_one_or_none()
    if resolved is None:
        raise DomainNotFoundError("Access grant not found")
    return resolved


def _profile_public_id(db: Session, profile_id: int) -> str:
    value = db.execute(
        select(PhrProfile.public_id).where(PhrProfile.id == profile_id)
    ).scalar_one_or_none()
    if value is None:
        raise DomainNotFoundError("Profile not found")
    return value


def _resolve_profile_id(db: Session, reference: str) -> int:
    selector = PhrProfile.public_id == reference
    if reference.isdecimal():
        selector = selector | (PhrProfile.id == int(reference))
    value = db.execute(select(PhrProfile.id).where(selector)).scalar_one_or_none()
    if value is None:
        raise DomainNotFoundError("Profile not found")
    return value


def _supporter_label(user: User | None) -> str:
    if user is None:
        return "Người hỗ trợ"
    if user.full_name.strip():
        return user.full_name.strip()
    local, _, domain = user.email.partition("@")
    if not domain:
        return "Người hỗ trợ"
    return f"{local[:2]}***@{domain}"


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
        return {
            "id": invitation.public_id,
            "token": raw_token,
            "expires_at": invitation.expires_at,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/invitations/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(
    payload: InvitationAcceptRequest | None = None,
    x_family_invitation_token: str | None = Header(
        default=None, alias="X-Family-Invitation-Token"
    ),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Accept an invitation without putting its capability in an URL."""

    raw_token = _invitation_capability(payload, x_family_invitation_token)
    recipient = current_user(db, token)
    try:
        grant = accept_family_invitation(db, recipient=recipient, raw_token=raw_token)
        db.commit()
        return {
            "id": grant.public_id,
            "profile_id": _profile_public_id(db, grant.profile_id),
            "object_type": grant.object_type,
            "object_id": grant.object_id,
            "data_classes": grant.data_classes_json,
            "allowed_actions": grant.allowed_actions_json,
            "purpose": grant.purpose,
            "expires_at": grant.expires_at,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/invitations/preview")
def preview_invitation(
    payload: InvitationAcceptRequest | None = None,
    x_family_invitation_token: str | None = Header(
        default=None, alias="X-Family-Invitation-Token"
    ),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Preview a recipient-bound invitation before the explicit accept write.

    The capability is accepted only in a JSON body/header, never in a path or
    query parameter. The service returns no health data, object identifier or
    inviter identity and does not consume/audit the invitation.
    """

    raw_token = _invitation_capability(payload, x_family_invitation_token)
    recipient = current_user(db, token)
    try:
        return preview_family_invitation(db, recipient=recipient, raw_token=raw_token)
    except (DomainNotFoundError, DomainValidationError) as error:
        _raise(error)


@router.post("/invitations/{invitation_token}/accept", deprecated=True)
def accept_invitation_legacy_url(
    invitation_token: str,
    _token: TokenPayload = USER,
) -> None:
    """Safe compatibility response for clients that still put capabilities in URLs.

    Deliberately do not process the capability: accepting it would preserve the
    query/path logging exposure this API change removes.  The secret is neither
    echoed nor added to audit records.
    """

    del invitation_token
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Use POST /family/invitations/accept with the capability in JSON "
            "or X-Family-Invitation-Token"
        ),
    )


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
            FamilyAccessGrant.starts_at <= now,
            FamilyAccessGrant.expires_at > now,
        )
        .order_by(FamilyAccessGrant.id.desc())
    ).scalars()
    rows = list(grants)
    users = {
        user.id: user
        for user in db.execute(
            select(User).where(
                User.id.in_({row.grantor_user_id for row in rows} or {-1})
            )
        ).scalars()
    }
    return [
        {
            "id": grant.public_id,
            "profile_id": _profile_public_id(db, grant.profile_id),
            "object_type": grant.object_type,
            "object_id": grant.object_id,
            "data_classes": grant.data_classes_json,
            "allowed_actions": grant.allowed_actions_json,
            "purpose": grant.purpose,
            "expires_at": grant.expires_at,
            "supporter_label": _supporter_label(users.get(grant.grantor_user_id)),
        }
        for grant in rows
    ]


@router.get("/notifications")
def family_notifications(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    """Return minimal in-app cards from live, explicitly delegated tasks only.

    There is no queued notification payload to clean up after revocation. A
    card is calculated against the active grant and the current task state on
    every request, so it disappears on revoke, expiry, or completion. Task
    titles, clinical notes, patient names, and free text intentionally never
    leave this endpoint.
    """

    caregiver = current_user(db, token)
    now = datetime.now(UTC)
    grants = list(
        db.execute(
            select(FamilyAccessGrant)
            .where(
                FamilyAccessGrant.grantee_user_id == caregiver.id,
                FamilyAccessGrant.object_type == "care_task",
                FamilyAccessGrant.status == "active",
                FamilyAccessGrant.revoked_at.is_(None),
                FamilyAccessGrant.starts_at <= now,
                FamilyAccessGrant.expires_at > now,
            )
            .order_by(FamilyAccessGrant.expires_at, FamilyAccessGrant.id)
        ).scalars()
    )
    cards: list[dict[str, Any]] = []
    for grant in grants:
        actions = grant.allowed_actions_json if isinstance(grant.allowed_actions_json, list) else []
        # A card is not a permission escalation: both seeing the task and
        # completing it have to be in the grant's exact action list.
        if "view" not in actions or "complete_task" not in actions:
            continue
        task_clauses = [LifeMapCareTask.public_id == grant.object_id]
        if grant.object_id.isdecimal():
            task_clauses.append(LifeMapCareTask.id == int(grant.object_id))
        task = db.execute(
            select(LifeMapCareTask).where(
                or_(*task_clauses),
                LifeMapCareTask.profile_id == grant.profile_id,
                LifeMapCareTask.status == "accepted",
            )
        ).scalar_one_or_none()
        if task is None:
            continue
        cards.append(
            {
                "id": (
                    f"family-task:{grant.public_id}:{task.public_id}:"
                    f"v{grant.grant_version}"
                ),
                "kind": "delegated_care_task",
                "profile_id": _profile_public_id(db, grant.profile_id),
                "grant_id": grant.public_id,
                "task_id": task.public_id,
                "purpose": grant.purpose,
                "expires_at": grant.expires_at,
                "action": "complete_task",
                "message": "Một nhiệm vụ chăm sóc đang chờ bạn xác nhận.",
            }
        )
    return cards


@router.post("/notifications/{grant_id}/{task_id}/acknowledge")
def acknowledge_notification(
    grant_id: str,
    task_id: str,
    payload: NotificationAcknowledgementRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    """Audit an acknowledgement after rechecking the live grant.

    ``grant_id`` is checked in addition to the service's exact object/action
    check so an old card cannot be acknowledged through a replacement grant.
    """

    caregiver = current_user(db, token)
    task_clauses = [LifeMapCareTask.public_id == task_id]
    if task_id.isdecimal():
        task_clauses.append(LifeMapCareTask.id == int(task_id))
    task = db.execute(
        select(LifeMapCareTask).where(or_(*task_clauses))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=403, detail="Family notification is no longer authorized")
    try:
        resolved_grant_id = _resolve_owned_grant_id(
            db,
            reference=grant_id,
            grantee_id=caregiver.id,
        )
    except DomainNotFoundError:
        raise HTTPException(
            status_code=403,
            detail="Family notification is no longer authorized",
        ) from None
    grant = db.execute(
        select(FamilyAccessGrant).where(
            FamilyAccessGrant.id == resolved_grant_id,
            FamilyAccessGrant.grantee_user_id == caregiver.id,
            FamilyAccessGrant.status == "active",
            FamilyAccessGrant.revoked_at.is_(None),
            FamilyAccessGrant.expires_at > datetime.now(UTC),
            FamilyAccessGrant.object_type == "care_task",
            FamilyAccessGrant.object_id.in_({task.public_id, str(task.id)}),
            FamilyAccessGrant.purpose == payload.purpose,
        )
    ).scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=403, detail="Family notification is no longer authorized")
    try:
        acknowledge_care_task_notification(
            db,
            caregiver=caregiver,
            profile_id=grant.profile_id,
            task_id=task.public_id,
            purpose=payload.purpose,
        )
        db.commit()
        return {"status": "acknowledged"}
    except (DomainAuthorizationError, DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.get("/access-grants")
def list_owner_grants(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    owner, profile = _profile(db, token)
    rows = list(
        db.execute(
            select(FamilyAccessGrant)
            .where(
                FamilyAccessGrant.grantor_user_id == owner.id,
                FamilyAccessGrant.profile_id == profile.id,
            )
            .order_by(FamilyAccessGrant.id.desc())
        ).scalars()
    )
    recipients = {
        user.id: user
        for user in db.execute(
            select(User).where(
                User.id.in_({row.grantee_user_id for row in rows} or {-1})
            )
        ).scalars()
    }
    return [
        {
            "id": grant.public_id,
            "supporter_label": _supporter_label(
                recipients.get(grant.grantee_user_id)
            ),
            "object_type": grant.object_type,
            "object_id": grant.object_id,
            "data_classes": grant.data_classes_json,
            "allowed_actions": grant.allowed_actions_json,
            "purpose": grant.purpose,
            "status": grant.status,
            "expires_at": grant.expires_at,
            "grant_version": grant.grant_version,
            "starts_at": grant.starts_at,
            "revoked_at": grant.revoked_at,
        }
        for grant in rows
    ]


@router.get("/share-options")
def family_share_options(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, list[dict[str, Any]]]:
    """Return only owner-controlled objects eligible for a new minimal grant."""

    owner, profile = _profile(db, token)
    del owner
    episodes = list(
        db.execute(
            select(LifeMapEpisode)
            .where(
                LifeMapEpisode.profile_id == profile.id,
                LifeMapEpisode.status.in_({"open", "active", "paused"}),
            )
            .order_by(LifeMapEpisode.updated_at.desc(), LifeMapEpisode.id.desc())
        ).scalars()
    )
    visits = list(
        db.execute(
            select(LifeMapVisit)
            .where(
                LifeMapVisit.profile_id == profile.id,
                LifeMapVisit.status.notin_({"cancelled"}),
            )
            .order_by(LifeMapVisit.updated_at.desc(), LifeMapVisit.id.desc())
        ).scalars()
    )
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == profile.id,
                LifeMapCareTask.status == "accepted",
            )
            .order_by(LifeMapCareTask.id.desc())
        ).scalars()
    )
    return {
        "episodes": [
            {"id": row.public_id, "label": row.title} for row in episodes
        ],
        "visits": [{"id": row.public_id, "label": row.title} for row in visits],
        "care_tasks": [
            {"id": row.public_id, "label": row.title} for row in tasks
        ],
    }


@router.post(
    "/access-grants/{grant_id}/renewals",
    status_code=status.HTTP_201_CREATED,
)
def renew_grant(
    grant_id: str,
    payload: GrantRenewalRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Issue a fresh one-time capability; never silently extend authorization."""

    owner = current_user(db, token)
    try:
        resolved_grant_id = _resolve_owned_grant_id(
            db, reference=grant_id, owner_id=owner.id
        )
        invitation, raw_token = create_family_grant_renewal(
            db,
            owner=owner,
            grant_id=resolved_grant_id,
            expires_at=payload.expires_at,
        )
        db.commit()
        return {
            "id": invitation.public_id,
            "token": raw_token,
            "expires_at": invitation.expires_at,
            "requires_recipient_acceptance": True,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.delete("/access-grants/{grant_id}")
def revoke_grant(
    grant_id: str, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    owner = current_user(db, token)
    try:
        resolved_grant_id = _resolve_owned_grant_id(
            db, reference=grant_id, owner_id=owner.id
        )
        grant = revoke_family_access_grant(
            db, owner=owner, grant_id=resolved_grant_id
        )
        db.commit()
        return {
            "id": grant.public_id,
            "status": grant.status,
            "grant_version": grant.grant_version,
        }
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@router.get("/access-log")
def access_log(db: Session = Depends(get_db), token: TokenPayload = USER) -> list[dict[str, Any]]:
    owner, profile = _profile(db, token)
    try:
        rows = list_family_access_log(db, owner=owner, profile_id=profile.id)
        grant_ids = {row.grant_id for row in rows if row.grant_id is not None}
        grant_public_ids = {
            grant.id: grant.public_id
            for grant in db.execute(
                select(FamilyAccessGrant).where(
                    FamilyAccessGrant.id.in_(grant_ids or {-1})
                )
            ).scalars()
        }
        return [
            {
                "id": row.public_id,
                "actor_label": (
                    "Bạn"
                    if row.actor_user_id == owner.id
                    else "Người hỗ trợ"
                    if row.actor_user_id is not None
                    else "Hệ thống"
                ),
                # Stable, locale-neutral presentation codes. Keep the legacy
                # actor_label/action/outcome fields below for older clients,
                # but let current web/mobile clients render these codes with
                # their own catalogs instead of coupling API data to Vietnamese
                # display text.
                "actor_code": _access_log_actor_code(row, owner_id=owner.id),
                "grant_id": (
                    grant_public_ids.get(row.grant_id)
                    if row.grant_id is not None
                    else None
                ),
                "object_type": row.object_type,
                "object_id": row.object_id,
                "action": row.action,
                "action_code": _access_log_action_code(row.action),
                "outcome": row.outcome,
                "outcome_code": _access_log_outcome_code(row.outcome),
                "purpose": row.purpose,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    except DomainNotFoundError as error:
        _raise(error)


def _access_log_actor_code(row: FamilyAccessLog, *, owner_id: int) -> str:
    if row.actor_user_id == owner_id:
        return "owner"
    if row.actor_user_id is not None:
        return "supporter"
    return "system"


def _access_log_action_code(value: str | None) -> str:
    # The ledger's raw action is preserved for audit compatibility. This
    # bounded presentation projection avoids turning future/internal actions
    # into untranslated client copy.
    return {
        "view": "view",
        "add_observation": "add_observation",
        "complete_task": "complete_task",
        "invitation.accept": "invitation_accept",
        "grant.revoke": "grant_revoke",
        "grant.renewal_invited": "grant_renewal_invited",
        "notification.acknowledged": "notification_acknowledged",
    }.get(str(value or "").strip().lower(), "other")


def _access_log_outcome_code(value: str | None) -> str:
    return {
        "success": "allowed",
        "allowed": "allowed",
        "denied": "denied",
        "failure": "failed",
        "failed": "failed",
    }.get(str(value or "").strip().lower(), "unknown")


@router.post("/profiles/{profile_id}/caregiver-observations", status_code=status.HTTP_201_CREATED)
def caregiver_observation(
    profile_id: str,
    payload: ObservationRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    caregiver = current_user(db, token)
    try:
        resolved_profile_id = _resolve_profile_id(db, profile_id)
        event = record_caregiver_observation(
            db,
            caregiver=caregiver,
            profile_id=resolved_profile_id,
            episode_id=payload.episode_id,
            purpose=payload.purpose,
            text=payload.text,
        )
        db.commit()
        return {
            "id": event.public_id,
            "truth_state": event.truth_state,
            "source": event.source_kind,
        }
    except (DomainAuthorizationError, DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/profiles/{profile_id}/care-tasks/{task_id}/complete")
def complete_task_as_caregiver(
    profile_id: str,
    task_id: str,
    payload: CompleteTaskRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    caregiver = current_user(db, token)
    try:
        resolved_profile_id = _resolve_profile_id(db, profile_id)
        task = complete_delegated_task(
            db,
            caregiver=caregiver,
            profile_id=resolved_profile_id,
            task_id=task_id,
            purpose=payload.purpose,
            evidence=payload.evidence,
        )
        db.commit()
        return {"id": task.public_id, "status": task.status, "completed_at": task.completed_at}
    except (DomainAuthorizationError, DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@task_router.post("/{task_id}/delegations", status_code=status.HTTP_201_CREATED)
def delegate_task(
    task_id: str,
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
        return {
            "id": invitation.public_id,
            "token": raw_token,
            "expires_at": invitation.expires_at,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)
