# ruff: noqa: B008
"""Compliance HTTP surface under ``/api/v1/compliance`` (Req 1-7).

Every route is flag-gated: when its governing ``COMPLIANCE_*`` flag is off the
endpoint returns a uniform ``{"enabled": false, ...}`` shape and performs no side
effect, so flags-off behavior equals the pre-feature baseline (Requirement 8.1,
8.2 / Correctness Property 6). CSRF on cookie-authenticated mutations is enforced
by the global middleware in ``main.py`` (Correctness Property 10). Admin records
are RBAC-gated (Correctness Property 7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.compliance import consent as consent_ledger
from clara_api.compliance import dsar as dsar_service
from clara_api.compliance.notice import current_notice_version, transparency_notice
from clara_api.compliance.records import records_manifest
from clara_api.compliance.service import ComplianceService
from clara_api.core.config import Settings, get_settings
from clara_api.core.rbac import get_current_token, require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import PhrProfile, User
from clara_api.db.session import get_db
from clara_api.lifemap.projection_invalidation import invalidate_projection_graph

router = APIRouter()

USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))
ADMIN_ROLE_DEP = Depends(require_roles("admin"))
AUTH_DEP = Depends(get_current_token)
SETTINGS_DEP = Depends(get_settings)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not exist",
        )
    return user


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ConsentMutationRequest(BaseModel):
    purpose: str = Field(min_length=1, max_length=64)
    policy_version: str = Field(default="", max_length=32)


class DsarRequestBody(BaseModel):
    kind: str = Field(min_length=1, max_length=16)


class DsarAdminStatusBody(BaseModel):
    request_id: int = Field(gt=0)
    status: str = Field(min_length=1, max_length=16)


# ---------------------------------------------------------------------------
# AI Transparency Notice (Req 1)
# ---------------------------------------------------------------------------


@router.get("/transparency-notice")
def get_transparency_notice(
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_transparency_notice_enabled:
        return {"enabled": False}
    user = _get_user_by_token(db, token)
    version = current_notice_version()
    acknowledged_version = consent_ledger.acknowledged_version(
        db, user_id=user.id, purpose=consent_ledger.PURPOSE_AI_TRANSPARENCY
    )
    # A new notice version requires re-acknowledgement (Req 1.6): the current
    # version counts as acknowledged only if the latest active grant matches it.
    acknowledged = acknowledged_version == version
    return {
        "enabled": True,
        "notice": transparency_notice(),
        "acknowledged": acknowledged,
        "acknowledged_version": acknowledged_version,
        "current_version": version,
    }


@router.post("/transparency-notice/ack")
def acknowledge_transparency_notice(
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_transparency_notice_enabled:
        return {"enabled": False}
    user = _get_user_by_token(db, token)
    version = current_notice_version()
    service = ComplianceService(db, settings)
    consent_ledger.grant(
        db, user_id=user.id, purpose=consent_ledger.PURPOSE_AI_TRANSPARENCY, version=version
    )
    service.record_event(
        "transparency_ack",
        user_id=user.id,
        meta={"notice_version": version},
    )
    db.commit()
    return {"enabled": True, "acknowledged": True, "current_version": version}


# ---------------------------------------------------------------------------
# Granular consent (Req 2)
# ---------------------------------------------------------------------------


@router.get("/consent")
def list_consent(
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_granular_consent_enabled:
        return {"enabled": False}
    user = _get_user_by_token(db, token)
    return {
        "enabled": True,
        "purposes": sorted(consent_ledger.COMPLIANCE_PURPOSES),
        "consents": consent_ledger.consent_summary(db, user_id=user.id),
    }


@router.post("/consent/grant")
def grant_consent(
    payload: ConsentMutationRequest,
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_granular_consent_enabled:
        return {"enabled": False}
    if not consent_ledger.is_valid_purpose(payload.purpose):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown consent purpose"
        )
    user = _get_user_by_token(db, token)
    ComplianceService(db, settings).grant_consent(
        user_id=user.id, purpose=payload.purpose, version=payload.policy_version
    )
    db.commit()
    return {"enabled": True, "purpose": payload.purpose, "granted": True}


@router.post("/consent/withdraw")
def withdraw_consent(
    payload: ConsentMutationRequest,
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_granular_consent_enabled:
        return {"enabled": False}
    if not consent_ledger.is_valid_purpose(payload.purpose):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown consent purpose"
        )
    user = _get_user_by_token(db, token)
    ComplianceService(db, settings).withdraw_consent(
        user_id=user.id, purpose=payload.purpose, version=payload.policy_version
    )
    profile_id = db.execute(
        select(PhrProfile.id).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile_id is not None:
        invalidate_projection_graph(
            db,
            profile_id=profile_id,
            reason=f"consent_withdrawn:{payload.purpose}",
            invalidate_all=True,
        )
    db.commit()
    return {"enabled": True, "purpose": payload.purpose, "granted": False}


# ---------------------------------------------------------------------------
# DSAR self-service (Req 3)
# ---------------------------------------------------------------------------


@router.post("/dsar/request")
def submit_dsar(
    payload: DsarRequestBody,
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_dsar_enabled:
        return {"enabled": False}
    if payload.kind not in dsar_service.DSAR_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown DSAR kind")
    user = _get_user_by_token(db, token)
    ack = dsar_service.DsarService(db, settings).request(user_id=user.id, kind=payload.kind)
    db.commit()
    return {
        "enabled": True,
        "request_id": ack.request_id,
        "kind": ack.kind,
        "status": ack.status,
        "created_at": ack.created_at.isoformat(),
        "due_at": ack.due_at.isoformat(),
        "statutory_window_days": ack.statutory_window_days,
    }


@router.get("/dsar/export")
def export_dsar(
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_dsar_enabled:
        return {"enabled": False}
    user = _get_user_by_token(db, token)
    service = dsar_service.DsarService(db, settings)
    service.request(user_id=user.id, kind="export")
    bundle = service.export(user=user)
    db.commit()
    return {"enabled": True, "export": bundle}


@router.post("/dsar/delete")
def delete_dsar(
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_dsar_enabled:
        return {"enabled": False}
    user = _get_user_by_token(db, token)
    service = dsar_service.DsarService(db, settings)
    # Irreversible anonymisation; transactional (Req 3.7 / Property 4). On a
    # partial failure the service rolls back and leaves the request in_progress.
    ack = service.delete(user=user)
    return {
        "enabled": True,
        "request_id": ack.request_id,
        "kind": ack.kind,
        "status": ack.status,
        "created_at": ack.created_at.isoformat(),
        "due_at": ack.due_at.isoformat(),
        "statutory_window_days": ack.statutory_window_days,
    }


def _dsar_record(row: Any, *, now: Any = None) -> dict[str, Any]:
    """Project a ``DsarRequest`` row into a PII-free API record.

    Carries only the request type, status, timestamps and an ``overdue`` flag
    derived from the statutory deadline — never the subject's identity.
    """

    overdue = (
        row.status not in dsar_service.RESOLVED_STATUSES
        and row.due_at is not None
        and (now or _utcnow()) > row.due_at
    )
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "overdue": overdue,
    }


@router.get("/dsar/requests")
def list_dsar_requests(
    token: TokenPayload = AUTH_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """List the authenticated subject's own DSAR requests (Req 3.6)."""

    if not settings.compliance_dsar_enabled:
        return {"enabled": False, "requests": []}
    user = _get_user_by_token(db, token)
    now = _utcnow()
    rows = dsar_service.DsarService(db, settings).list_for_user(user_id=user.id)
    return {"enabled": True, "requests": [_dsar_record(r, now=now) for r in rows]}


# ---------------------------------------------------------------------------
# Admin DSAR queue (Req 3.6) — RBAC-gated (Property 7)
# ---------------------------------------------------------------------------


@router.get("/dsar/admin/queue")
def admin_dsar_queue(
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Global DSAR queue for admins, ordered by statutory urgency (Req 3.6).

    Admin-only (Correctness Property 7); rows contain no PII. Tracks resolution
    against the statutory window via per-row ``overdue`` flags.
    """

    if not settings.compliance_dsar_enabled:
        return {"enabled": False, "requests": [], "overdue_count": 0}
    now = _utcnow()
    rows = dsar_service.DsarService(db, settings).admin_queue()
    records = [_dsar_record(r, now=now) for r in rows]
    overdue_count = sum(1 for r in records if r["overdue"])
    return {
        "enabled": True,
        "requests": records,
        "overdue_count": overdue_count,
        "statutory_window_days": dsar_service.DsarService(db, settings).statutory_window_days,
    }


@router.post("/dsar/admin/status")
def admin_set_dsar_status(
    payload: DsarAdminStatusBody,
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Update a DSAR request's resolution status (admin queue action, Req 3.6).

    Admin-only (Correctness Property 7). The mutation is recorded as a PII-free
    compliance event keyed on the row's opaque reference.
    """

    if not settings.compliance_dsar_enabled:
        return {"enabled": False}
    try:
        row = dsar_service.DsarService(db, settings).set_status(
            request_id=payload.request_id, status=payload.status
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return {"enabled": True, **_dsar_record(row)}


# ---------------------------------------------------------------------------
# Admin compliance records (Req 6) — RBAC-gated (Property 7)
# ---------------------------------------------------------------------------


@router.get("/records")
def get_records(
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not settings.compliance_records_admin_enabled:
        return {"enabled": False}
    return {"enabled": True, "records": records_manifest(db)}
