"""Admin-action audit-read endpoint (Requirement 9.4).

This module exposes the read surface for the append-only admin-action audit
trail implemented in :mod:`clara_api.observability.admin_audit`. It declares a
single admin-gated ``GET`` route that returns the recorded admin-action audit
records most-recent-first via ``list_admin_actions(db)``.

Like the other flag-gated admin surfaces (``admin_rag.py`` ingestion controls,
``system.py`` analytics), the endpoint ships dark: when ``admin_audit_log_enabled``
is off it returns the project's standard "feature-disabled" HTTP 404 shape rather
than a partial/empty success, so the surface is invisible until the audit trail
is turned on (Requirements 12.2, 12.4). The flag check runs inside the handler
body so the ``require_roles("admin")`` dependency still authorizes the caller
first (403 for non-admin, 401 for a missing/invalid token — Requirement 1.1).

The records are already PII-free by construction (opaque ``actor_ref`` + a
PII-projected ``meta_json``), so the response carries no PII (Requirements 9.3,
11.3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.session import get_db
from clara_api.observability.admin_audit import list_admin_actions

router = APIRouter()

# Single admin RBAC dependency reused by every route (Requirement 1.1), mirroring
# the ``ADMIN_ROLE_DEP`` convention used by ``admin_rag.py``.
ADMIN_ROLE_DEP = Depends(require_roles("admin"))

# Upper bound on the number of records returned in one read so the response stays
# bounded regardless of trail size.
_AUDIT_READ_MAX_LIMIT = 500


class AdminAuditRecordResponse(BaseModel):
    """One PII-free admin-action audit record (mirrors ``AdminAuditRecord.as_dict``)."""

    model_config = ConfigDict(extra="allow")

    id: int
    actor_ref: str
    action: str
    target: str = ""
    outcome: str = ""
    meta: dict = Field(default_factory=dict)
    created_at: str | None = None


class AdminAuditListResponse(BaseModel):
    """Admin-action audit records ordered most-recent-first (Requirement 9.4)."""

    records: list[AdminAuditRecordResponse] = Field(default_factory=list)


@router.get("", response_model=AdminAuditListResponse)
def list_admin_audit(
    limit: int = Query(
        default=100,
        ge=1,
        le=_AUDIT_READ_MAX_LIMIT,
        description="Maximum number of records to return (most-recent-first).",
    ),
    _token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> AdminAuditListResponse:
    """Return admin-action audit records most-recent-first (Requirement 9.4).

    Admin-only (403 non-admin / 401 no token). When ``admin_audit_log_enabled``
    is off the endpoint returns the standard feature-disabled HTTP 404 shape so
    the surface ships dark (Requirements 12.2, 12.4). The records are PII-free by
    construction; no update/delete path is exposed (Requirement 9.2).
    """

    if not get_settings().admin_audit_log_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nhật ký kiểm toán quản trị đã bị tắt.",
        )

    rows = list_admin_actions(db, limit=limit)
    return AdminAuditListResponse(
        records=[AdminAuditRecordResponse.model_validate(row.as_dict()) for row in rows]
    )
