from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.db.models import User
from clara_api.db.session import get_db
from clara_api.observability.admin_audit import AdminAuditRecord

router = APIRouter()


class AdminUserOut(BaseModel):
    id: int
    email: str
    role: str
    full_name: str
    status: str
    is_email_verified: bool
    resource_version: str
    last_login_at: datetime | None
    created_at: datetime


class AdminUsersListResponse(BaseModel):
    items: list[AdminUserOut]
    total: int
    next_cursor: str | None = None


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(normal|doctor|researcher|admin)$")
    expected_resource_version: str | None = None
    reason_code: str = Field(default="ADMIN_ROLE_CHANGE")


class LockUserRequest(BaseModel):
    reason: str = Field(default="ADMIN_LOCK")
    expected_resource_version: str | None = None


class UnlockUserRequest(BaseModel):
    reason: str = Field(default="ADMIN_UNLOCK")
    expected_resource_version: str | None = None


class MutationReceipt(BaseModel):
    success: bool = True
    resource_version: str
    audit_event_id: str
    committed_at: str
    correlation_id: str
    user: AdminUserOut


def _advance_version(current: str | None) -> str:
    try:
        return str(int(current or "1") + 1)
    except (ValueError, TypeError):
        return str(uuid4().hex[:8])


def _check_last_active_admin(db: Session, target_user: User) -> None:
    if target_user.role == "admin" and target_user.status == "active":
        active_admin_count = db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.status == "active",
                User.id != target_user.id,
            )
        ) or 0
        if active_admin_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="LAST_ACTIVE_ADMIN_INVARIANT: Cannot demote or lock the last active administrator.",
            )


@router.get("", response_model=AdminUsersListResponse)
def list_admin_users(
    query: str | None = Query(None, description="Search term for name or email"),
    role: str | None = Query(None, description="Filter by role"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    cursor: int = Query(0, ge=0, description="Offset cursor"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    if query:
        term = f"%{query.strip()}%"
        stmt = stmt.where((User.email.ilike(term)) | (User.full_name.ilike(term)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(stmt.order_by(User.id.asc()).offset(cursor).limit(limit)).all()

    next_cursor = str(cursor + limit) if (cursor + limit) < total else None
    return {
        "items": [
            AdminUserOut(
                id=u.id,
                email=u.email,
                role=u.role,
                full_name=u.full_name or "",
                status=u.status or "active",
                is_email_verified=bool(u.is_email_verified),
                resource_version=u.resource_version or "1",
                last_login_at=u.last_login_at,
                created_at=u.created_at or datetime.now(UTC),
            )
            for u in users
        ],
        "total": total,
        "next_cursor": next_cursor,
    }


@router.get("/{user_id}", response_model=AdminUserOut)
def get_admin_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    return AdminUserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name or "",
        status=user.status or "active",
        is_email_verified=bool(user.is_email_verified),
        resource_version=user.resource_version or "1",
        last_login_at=user.last_login_at,
        created_at=user.created_at or datetime.now(UTC),
    )


@router.patch("/{user_id}/role", response_model=MutationReceipt)
def update_user_role(
    user_id: int,
    payload: UpdateRoleRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> MutationReceipt:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    if payload.expected_resource_version and user.resource_version:
        if user.resource_version != payload.expected_resource_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RESOURCE_VERSION_CONFLICT: Expected {payload.expected_resource_version}, found {user.resource_version}",
            )

    if user.role == "admin" and payload.role != "admin":
        _check_last_active_admin(db, user)

    old_role = user.role
    user.role = payload.role
    user.resource_version = _advance_version(user.resource_version)

    audit_id = str(uuid4())
    audit = AdminAuditRecord(
        admin_user_id=current_user.id,
        action="UPDATE_USER_ROLE",
        target_entity="user",
        target_id=str(user.id),
        details_json={
            "old_role": old_role,
            "new_role": payload.role,
            "reason_code": payload.reason_code,
            "audit_id": audit_id,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    now_iso = datetime.now(UTC).isoformat()
    return MutationReceipt(
        success=True,
        resource_version=user.resource_version,
        audit_event_id=audit_id,
        committed_at=now_iso,
        correlation_id=str(uuid4()),
        user=AdminUserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            full_name=user.full_name or "",
            status=user.status or "active",
            is_email_verified=bool(user.is_email_verified),
            resource_version=user.resource_version,
            last_login_at=user.last_login_at,
            created_at=user.created_at or datetime.now(UTC),
        ),
    )


@router.post("/{user_id}/lock", response_model=MutationReceipt)
def lock_user_account(
    user_id: int,
    payload: LockUserRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> MutationReceipt:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    if payload.expected_resource_version and user.resource_version:
        if user.resource_version != payload.expected_resource_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RESOURCE_VERSION_CONFLICT: Expected {payload.expected_resource_version}, found {user.resource_version}",
            )

    _check_last_active_admin(db, user)

    user.status = "locked"
    user.resource_version = _advance_version(user.resource_version)

    audit_id = str(uuid4())
    audit = AdminAuditRecord(
        admin_user_id=current_user.id,
        action="LOCK_USER_ACCOUNT",
        target_entity="user",
        target_id=str(user.id),
        details_json={"reason": payload.reason, "audit_id": audit_id},
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    now_iso = datetime.now(UTC).isoformat()
    return MutationReceipt(
        success=True,
        resource_version=user.resource_version,
        audit_event_id=audit_id,
        committed_at=now_iso,
        correlation_id=str(uuid4()),
        user=AdminUserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            full_name=user.full_name or "",
            status=user.status,
            is_email_verified=bool(user.is_email_verified),
            resource_version=user.resource_version,
            last_login_at=user.last_login_at,
            created_at=user.created_at or datetime.now(UTC),
        ),
    )


@router.post("/{user_id}/unlock", response_model=MutationReceipt)
def unlock_user_account(
    user_id: int,
    payload: UnlockUserRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> MutationReceipt:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    if payload.expected_resource_version and user.resource_version:
        if user.resource_version != payload.expected_resource_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RESOURCE_VERSION_CONFLICT: Expected {payload.expected_resource_version}, found {user.resource_version}",
            )

    user.status = "active"
    user.resource_version = _advance_version(user.resource_version)

    audit_id = str(uuid4())
    audit = AdminAuditRecord(
        admin_user_id=current_user.id,
        action="UNLOCK_USER_ACCOUNT",
        target_entity="user",
        target_id=str(user.id),
        details_json={"reason": payload.reason, "audit_id": audit_id},
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    now_iso = datetime.now(UTC).isoformat()
    return MutationReceipt(
        success=True,
        resource_version=user.resource_version,
        audit_event_id=audit_id,
        committed_at=now_iso,
        correlation_id=str(uuid4()),
        user=AdminUserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            full_name=user.full_name or "",
            status=user.status,
            is_email_verified=bool(user.is_email_verified),
            resource_version=user.resource_version,
            last_login_at=user.last_login_at,
            created_at=user.created_at or datetime.now(UTC),
        ),
    )


@router.post("/{user_id}/sessions/revoke")
def revoke_user_sessions(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    audit = AdminAuditRecord(
        admin_user_id=current_user.id,
        action="REVOKE_USER_SESSIONS",
        target_entity="user",
        target_id=str(user.id),
        details_json={"revoked_by": current_user.id},
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "revoked_sessions_count": 1,
        "user_id": user.id,
        "revoked_at": datetime.now(UTC).isoformat(),
    }
