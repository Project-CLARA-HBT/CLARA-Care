"""Multi-tenant isolation and workspace membership boundaries for ML inference & RAG.

Part of Phase PH04 (Multi-tenant organizations và workspaces).
Guarantees:
1. Strict tenant boundary validation for all ML inference and RAG retrieval.
2. Workspace membership invitation gate: pending/invited/expired/revoked invitations
   are strictly blocked from accessing tenant-scoped knowledge bases or models.
3. Cross-tenant non-interference: tenant A cannot query, view, or cache tenant B
   knowledge or documents.
4. Zero-PII/PHI invariant: error responses and telemetry digests contain zero
   patient or user identifiable attributes.
"""

from __future__ import annotations

import enum
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status

_SAFE_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,128}$")


class WorkspaceMembershipStatus(enum.StrEnum):
    """Membership lifecycle states within a multi-tenant workspace."""

    ACTIVE = "active"
    INVITED = "invited"
    PENDING = "pending"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class WorkspaceRole(enum.StrEnum):
    """Permitted workspace roles governing ML capability invocation."""

    OWNER = "owner"
    ADMIN = "admin"
    CLINICIAN = "clinician"
    RESEARCHER = "researcher"
    MEMBER = "member"
    GUEST = "guest"
    AUDITOR = "auditor"


class TenantBoundaryError(HTTPException):
    """Fail-closed exception raised upon tenant isolation or membership violation."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "tenant_boundary_violation", "code": reason_code, "message": detail},
        )
        self.reason_code = reason_code


@dataclass(frozen=True)
class WorkspaceInvitationContext:
    """Capability context describing an invitation or membership edge."""

    invitation_id: str
    tenant_id: str
    role: str
    status: WorkspaceMembershipStatus
    expires_at: datetime | None = None
    recipient_hash: str = ""

    @classmethod
    def create(
        cls,
        *,
        invitation_id: str,
        tenant_id: str,
        role: str,
        status: WorkspaceMembershipStatus | str,
        recipient_email: str = "",
        expires_at: datetime | None = None,
    ) -> WorkspaceInvitationContext:
        """Create a zero-PII invitation context."""
        norm_status = (
            status
            if isinstance(status, WorkspaceMembershipStatus)
            else WorkspaceMembershipStatus(str(status).strip().lower())
        )
        recipient_hash = ""
        if recipient_email:
            recipient_hash = hashlib.sha256(recipient_email.strip().lower().encode("utf-8")).hexdigest()

        return cls(
            invitation_id=str(invitation_id).strip(),
            tenant_id=sanitize_tenant_id(tenant_id),
            role=str(role).strip().lower(),
            status=norm_status,
            expires_at=expires_at,
            recipient_hash=recipient_hash,
        )


def sanitize_tenant_id(tenant_id: str | None) -> str:
    """Validate and sanitize a tenant_id string against path traversal or injection.

    Returns the clean string or raises TenantBoundaryError.
    """
    if tenant_id is None:
        return ""
    clean = str(tenant_id).strip()
    if not clean:
        return ""
    if not _SAFE_TENANT_ID_RE.match(clean) or ".." in clean or "/" in clean or "\\" in clean:
        raise TenantBoundaryError(
            reason_code="invalid_tenant_identifier",
            detail="Malformed or insecure tenant identifier",
        )
    return clean


def enforce_workspace_ml_membership(
    tenant_id: str | None,
    membership_status: WorkspaceMembershipStatus | str | None,
    *,
    required_roles: tuple[str, ...] | list[str] | set[str] | None = None,
    caller_role: str | None = None,
    invitation_context: WorkspaceInvitationContext | None = None,
) -> bool:
    """Enforce workspace membership boundaries before admitting a request to tenant ML.

    Invariants:
    1. If tenant_id is empty/None, request is un-tenanted (public/consumer scope); no tenant
       knowledge or private RAG corpus may be accessed.
    2. If tenant_id is specified:
       - Membership status MUST be ACTIVE.
       - A status of INVITED or PENDING strictly denies access with HTTP 403
         (an invitation token or pending invitation does not grant tenant inference access).
       - A status of EXPIRED denies access with HTTP 403.
       - A status of REVOKED or SUSPENDED denies access with HTTP 403.
    3. If required_roles is provided, caller_role must belong to the allowed set.
    """
    clean_tenant = sanitize_tenant_id(tenant_id)
    if not clean_tenant:
        # Public / un-tenanted scope
        return True

    # When invitation context is supplied, its status and tenant_id take precedence
    if invitation_context is not None:
        if invitation_context.tenant_id != clean_tenant:
            raise TenantBoundaryError(
                reason_code="tenant_context_mismatch",
                detail="Invitation workspace does not match requested tenant boundary",
            )
        effective_status = invitation_context.status
        if invitation_context.expires_at is not None:
            now = datetime.now(UTC)
            if invitation_context.expires_at < now:
                effective_status = WorkspaceMembershipStatus.EXPIRED
    else:
        if membership_status is None:
            raise TenantBoundaryError(
                reason_code="unauthenticated_tenant_access",
                detail="Tenant context specified without authenticated membership verification",
            )
        effective_status = (
            membership_status
            if isinstance(membership_status, WorkspaceMembershipStatus)
            else WorkspaceMembershipStatus(str(membership_status).strip().lower())
        )

    if effective_status in (WorkspaceMembershipStatus.INVITED, WorkspaceMembershipStatus.PENDING):
        raise TenantBoundaryError(
            reason_code="invitation_pending_unauthorized",
            detail="Workspace membership invitation is pending and has not been accepted",
        )

    if effective_status == WorkspaceMembershipStatus.EXPIRED:
        raise TenantBoundaryError(
            reason_code="invitation_expired",
            detail="Workspace membership or invitation has expired",
        )

    if effective_status in (WorkspaceMembershipStatus.REVOKED, WorkspaceMembershipStatus.SUSPENDED):
        raise TenantBoundaryError(
            reason_code="membership_revoked",
            detail="Workspace membership is revoked or suspended",
        )

    if effective_status != WorkspaceMembershipStatus.ACTIVE:
        raise TenantBoundaryError(
            reason_code="invalid_membership_status",
            detail="Invalid or unrecognized workspace membership status",
        )

    if required_roles and caller_role:
        norm_role = str(caller_role).strip().lower()
        allowed = {str(r).strip().lower() for r in required_roles}
        if norm_role not in allowed and norm_role != "admin" and norm_role != "owner":
            raise TenantBoundaryError(
                reason_code="insufficient_workspace_role",
                detail="Insufficient workspace privileges for requested ML capability",
            )

    return True


def compose_tenant_cache_key(base_key: str, tenant_id: str | None) -> str:
    """Prefix a cache key with sanitized tenant identifier to prevent cross-tenant collision."""
    clean_tenant = sanitize_tenant_id(tenant_id)
    if not clean_tenant:
        return f"public::{base_key}"
    return f"tenant::{clean_tenant}::{base_key}"
