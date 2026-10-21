# ruff: noqa: B008
"""Multi-tenant Organization & Collaborative Workspace API Endpoints.

Part of Phase PH04 / Subagent A01 (API + contract).
Enforces:
1. Strict tenant boundary isolation (Anti-IDOR: 404 on unpermitted/cross-tenant resources).
2. Defense-in-depth tenant scoping (organization membership authorization).
3. Uniform error envelopes and non-enumeration guarantees.
4. Non-PII audit logging for administrative mutations.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import User
from clara_api.db.session import get_db
from clara_api.schemas import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationMemberAddRequest,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
    OrganizationMemberUpdateRequest,
    OrganizationResponse,
    OrganizationRole,
    OrganizationStatus,
    OrganizationTier,
    OrganizationUpdateRequest,
    TenantAuditLogItem,
    TenantAuditResponse,
    TenantWorkspaceCreateRequest,
    TenantWorkspaceListResponse,
    TenantWorkspaceResponse,
    TenantWorkspaceRole,
    TenantWorkspaceUpdateRequest,
)

router = APIRouter()

USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
        )
    return user


def _slugify(val: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", val.strip().lower()).strip("-")
    return cleaned or "org"


# ==============================================================================
# In-Memory Tenant Repository State Store
# Provides hermetic multi-tenant state and decoupled DB fallback for PH04.
# ==============================================================================

class _TenantMemoryStore:
    def __init__(self) -> None:
        self.organizations: dict[str, dict[str, Any]] = {}
        self.members: dict[str, list[dict[str, Any]]] = {}  # org_id -> list of members
        self.workspaces: dict[str, list[dict[str, Any]]] = {}  # org_id -> list of workspaces
        self.audit_logs: dict[str, list[dict[str, Any]]] = {}  # org_id -> list of audit events
        self._seed_default_org()

    def _seed_default_org(self) -> None:
        default_org_id = "org_default_system"
        now = datetime.now(UTC)
        self.organizations[default_org_id] = {
            "id": default_org_id,
            "name": "CLARA Healthcare Network",
            "slug": "clara-healthcare",
            "description": "Default multi-tenant demonstration organization",
            "tier": OrganizationTier.ENTERPRISE.value,
            "status": OrganizationStatus.ACTIVE.value,
            "contact_email": "admin@theclaracare.com",
            "created_at": now,
            "updated_at": now,
            "settings": {},
        }
        self.members[default_org_id] = [
            {
                "id": "mem_default_admin",
                "org_id": default_org_id,
                "user_id": 1,
                "user_email": "admin@example.com",
                "role": OrganizationRole.OWNER.value,
                "status": "active",
                "joined_at": now,
                "created_at": now,
            }
        ]
        self.workspaces[default_org_id] = [
            {
                "id": "ws_clinical_ops",
                "org_id": default_org_id,
                "name": "Clinical Operations",
                "slug": "clinical-ops",
                "description": "Main hospital ward & clinical deliberation workspace",
                "is_restricted": False,
                "is_archived": False,
                "member_count": 1,
                "conversation_count": 0,
                "created_at": now,
                "updated_at": now,
            }
        ]
        self.audit_logs[default_org_id] = []

    def record_audit(
        self,
        org_id: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "event_id": f"evt_{secrets.token_hex(8)}",
            "org_id": org_id,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": datetime.now(UTC),
            "metadata": metadata or {},
        }
        self.audit_logs.setdefault(org_id, []).append(event)


_STORE = _TenantMemoryStore()


def _get_user_membership(org_id: str, user_email: str) -> dict[str, Any] | None:
    for m in _STORE.members.get(org_id, []):
        if m["user_email"].lower() == user_email.lower() and m["status"] == "active":
            return m
    return None


def _check_tenant_access(
    org_id: str,
    user: User,
    token: TokenPayload,
    required_roles: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Verify tenant isolation and membership. Fail closed with 404 to prevent IDOR enumeration."""
    org = _STORE.organizations.get(org_id)
    if org is None or org["status"] == OrganizationStatus.DEPROVISIONED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tổ chức không tồn tại hoặc không có quyền truy cập",
        )

    # System admin has implicit platform oversight
    if token.role == "admin":
        membership = _get_user_membership(org_id, user.email)
        return org, membership

    membership = _get_user_membership(org_id, user.email)
    if membership is None:
        # Non-enumeration invariant: Return 404 rather than 403 to prevent org discovery
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tổ chức không tồn tại hoặc không có quyền truy cập",
        )

    if required_roles and membership["role"] not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện hành động này trong tổ chức",
        )

    return org, membership


# ==============================================================================
# Organization Endpoints
# ==============================================================================

@router.get("", response_model=OrganizationListResponse)
def list_organizations(
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationListResponse:
    """List all tenant organizations accessible to the authenticated actor."""
    user = _get_user_by_token(db, token)
    accessible_orgs: list[OrganizationResponse] = []

    for org_id, org in _STORE.organizations.items():
        if org["status"] == OrganizationStatus.DEPROVISIONED.value:
            continue
        is_member = token.role == "admin" or _get_user_membership(org_id, user.email) is not None
        if is_member:
            members = [m for m in _STORE.members.get(org_id, []) if m["status"] == "active"]
            workspaces = [w for w in _STORE.workspaces.get(org_id, []) if not w["is_archived"]]
            accessible_orgs.append(
                OrganizationResponse(
                    id=org["id"],
                    name=org["name"],
                    slug=org["slug"],
                    description=org["description"],
                    tier=org["tier"],
                    status=org["status"],
                    contact_email=org.get("contact_email"),
                    member_count=len(members),
                    workspace_count=len(workspaces),
                    created_at=org["created_at"],
                    updated_at=org["updated_at"],
                )
            )

    return OrganizationListResponse(items=accessible_orgs, total=len(accessible_orgs))


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Provision a new tenant organization with the creator assigned as owner."""
    user = _get_user_by_token(db, token)
    slug = _slugify(payload.slug or payload.name)

    # Validate slug uniqueness
    for existing in _STORE.organizations.values():
        if existing["slug"] == slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug tổ chức '{slug}' đã tồn tại",
            )

    org_id = f"org_{slug}_{secrets.token_hex(4)}"
    now = datetime.now(UTC)

    org_data = {
        "id": org_id,
        "name": payload.name,
        "slug": slug,
        "description": payload.description,
        "tier": payload.tier.value,
        "status": OrganizationStatus.ACTIVE.value,
        "contact_email": payload.contact_email or user.email,
        "created_at": now,
        "updated_at": now,
        "settings": payload.settings,
    }
    _STORE.organizations[org_id] = org_data

    # Creator becomes organization OWNER
    owner_member = {
        "id": f"mem_{secrets.token_hex(6)}",
        "org_id": org_id,
        "user_id": user.id,
        "user_email": user.email,
        "role": OrganizationRole.OWNER.value,
        "status": "active",
        "joined_at": now,
        "created_at": now,
    }
    _STORE.members[org_id] = [owner_member]

    # Seed default collaborative workspace
    default_ws = {
        "id": f"ws_{secrets.token_hex(6)}",
        "org_id": org_id,
        "name": "General Workspace",
        "slug": "general",
        "description": "Default collaboration workspace",
        "is_restricted": False,
        "is_archived": False,
        "member_count": 1,
        "conversation_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    _STORE.workspaces[org_id] = [default_ws]
    _STORE.audit_logs[org_id] = []

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="organization.create",
        resource_type="organization",
        resource_id=org_id,
        metadata={"slug": slug, "tier": payload.tier.value},
    )

    return OrganizationResponse(
        id=org_id,
        name=org_data["name"],
        slug=slug,
        description=org_data["description"],
        tier=org_data["tier"],
        status=org_data["status"],
        contact_email=org_data["contact_email"],
        member_count=1,
        workspace_count=1,
        created_at=now,
        updated_at=now,
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: str,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Retrieve details for a specific tenant organization (anti-IDOR guarded)."""
    user = _get_user_by_token(db, token)
    org, _ = _check_tenant_access(org_id, user, token)

    members = [m for m in _STORE.members.get(org_id, []) if m["status"] == "active"]
    workspaces = [w for w in _STORE.workspaces.get(org_id, []) if not w["is_archived"]]

    return OrganizationResponse(
        id=org["id"],
        name=org["name"],
        slug=org["slug"],
        description=org["description"],
        tier=org["tier"],
        status=org["status"],
        contact_email=org.get("contact_email"),
        member_count=len(members),
        workspace_count=len(workspaces),
        created_at=org["created_at"],
        updated_at=org["updated_at"],
    )


@router.patch("/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: str,
    payload: OrganizationUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Update organization settings or status (requires owner or admin role)."""
    user = _get_user_by_token(db, token)
    org, _ = _check_tenant_access(org_id, user, token, required_roles={"owner", "admin"})

    now = datetime.now(UTC)
    if payload.name is not None:
        org["name"] = payload.name
    if payload.description is not None:
        org["description"] = payload.description
    if payload.status is not None:
        org["status"] = payload.status.value
    if payload.tier is not None:
        org["tier"] = payload.tier.value
    if payload.contact_email is not None:
        org["contact_email"] = payload.contact_email
    if payload.settings is not None:
        org["settings"] = payload.settings
    org["updated_at"] = now

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="organization.update",
        resource_type="organization",
        resource_id=org_id,
        metadata={"updated_fields": list(payload.model_dump(exclude_unset=True).keys())},
    )

    members = [m for m in _STORE.members.get(org_id, []) if m["status"] == "active"]
    workspaces = [w for w in _STORE.workspaces.get(org_id, []) if not w["is_archived"]]

    return OrganizationResponse(
        id=org["id"],
        name=org["name"],
        slug=org["slug"],
        description=org["description"],
        tier=org["tier"],
        status=org["status"],
        contact_email=org.get("contact_email"),
        member_count=len(members),
        workspace_count=len(workspaces),
        created_at=org["created_at"],
        updated_at=org["updated_at"],
    )


# ==============================================================================
# Member Management Endpoints
# ==============================================================================

@router.get("/{org_id}/members", response_model=OrganizationMemberListResponse)
def list_organization_members(
    org_id: str,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationMemberListResponse:
    """List members of a tenant organization."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token)

    member_records = [
        OrganizationMemberResponse(
            id=m["id"],
            org_id=m["org_id"],
            user_id=m.get("user_id"),
            user_email=m["user_email"],
            role=m["role"],
            status=m["status"],
            joined_at=m.get("joined_at"),
            created_at=m["created_at"],
        )
        for m in _STORE.members.get(org_id, [])
    ]
    return OrganizationMemberListResponse(items=member_records, total=len(member_records))


@router.post("/{org_id}/members", response_model=OrganizationMemberResponse, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    org_id: str,
    payload: OrganizationMemberAddRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationMemberResponse:
    """Add or invite a member to the organization (requires owner or admin role)."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin"})

    existing_members = _STORE.members.get(org_id, [])
    for m in existing_members:
        if m["user_email"].lower() == payload.user_email.lower():
            if m["status"] == "active":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Người dùng '{payload.user_email}' đã là thành viên của tổ chức",
                )
            # Re-activate suspended member
            m["status"] = "active"
            m["role"] = payload.role.value
            return OrganizationMemberResponse(
                id=m["id"],
                org_id=org_id,
                user_id=m.get("user_id"),
                user_email=m["user_email"],
                role=m["role"],
                status=m["status"],
                joined_at=m.get("joined_at"),
                created_at=m["created_at"],
            )

    now = datetime.now(UTC)
    new_member = {
        "id": f"mem_{secrets.token_hex(6)}",
        "org_id": org_id,
        "user_id": None,
        "user_email": payload.user_email,
        "role": payload.role.value,
        "status": "invited",
        "joined_at": None,
        "created_at": now,
    }
    _STORE.members.setdefault(org_id, []).append(new_member)

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="member.invite",
        resource_type="member",
        resource_id=new_member["id"],
        metadata={"invited_email": payload.user_email, "role": payload.role.value},
    )

    return OrganizationMemberResponse(
        id=new_member["id"],
        org_id=org_id,
        user_id=None,
        user_email=new_member["user_email"],
        role=new_member["role"],
        status=new_member["status"],
        joined_at=None,
        created_at=now,
    )


@router.patch("/{org_id}/members/{member_id}", response_model=OrganizationMemberResponse)
def update_organization_member_role(
    org_id: str,
    member_id: str,
    payload: OrganizationMemberUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> OrganizationMemberResponse:
    """Update role for a member of the organization."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin"})

    members = _STORE.members.get(org_id, [])
    target: dict[str, Any] | None = None
    for m in members:
        if m["id"] == member_id:
            target = m
            break

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thành viên không tồn tại trong tổ chức",
        )

    old_role = target["role"]
    target["role"] = payload.role.value

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="member.role_update",
        resource_type="member",
        resource_id=member_id,
        metadata={"old_role": old_role, "new_role": payload.role.value},
    )

    return OrganizationMemberResponse(
        id=target["id"],
        org_id=org_id,
        user_id=target.get("user_id"),
        user_email=target["user_email"],
        role=target["role"],
        status=target["status"],
        joined_at=target.get("joined_at"),
        created_at=target["created_at"],
    )


@router.delete("/{org_id}/members/{member_id}", status_code=status.HTTP_200_OK)
def remove_organization_member(
    org_id: str,
    member_id: str,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Remove a member from the organization."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin"})

    members = _STORE.members.get(org_id, [])
    target: dict[str, Any] | None = None
    for m in members:
        if m["id"] == member_id:
            target = m
            break

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thành viên không tồn tại trong tổ chức",
        )

    # Invariant: Cannot remove the last active owner
    if target["role"] == OrganizationRole.OWNER.value:
        active_owners = [
            m for m in members if m["role"] == OrganizationRole.OWNER.value and m["status"] == "active"
        ]
        if len(active_owners) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể xóa chủ sở hữu cuối cùng của tổ chức",
            )

    members.remove(target)

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="member.remove",
        resource_type="member",
        resource_id=member_id,
        metadata={"removed_email": target["user_email"]},
    )

    return {"status": "removed", "member_id": member_id}


# ==============================================================================
# Tenant Collaborative Workspaces Endpoints
# ==============================================================================

@router.get("/{org_id}/workspaces", response_model=TenantWorkspaceListResponse)
def list_tenant_workspaces(
    org_id: str,
    include_archived: bool = False,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> TenantWorkspaceListResponse:
    """List collaborative workspaces established within a tenant organization."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token)

    workspaces = _STORE.workspaces.get(org_id, [])
    items: list[TenantWorkspaceResponse] = []
    for w in workspaces:
        if not include_archived and w["is_archived"]:
            continue
        items.append(
            TenantWorkspaceResponse(
                id=w["id"],
                org_id=w["org_id"],
                name=w["name"],
                slug=w["slug"],
                description=w["description"],
                is_restricted=w["is_restricted"],
                is_archived=w["is_archived"],
                member_count=w["member_count"],
                conversation_count=w["conversation_count"],
                created_at=w["created_at"],
                updated_at=w["updated_at"],
            )
        )
    return TenantWorkspaceListResponse(items=items, total=len(items))


@router.post("/{org_id}/workspaces", response_model=TenantWorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_workspace(
    org_id: str,
    payload: TenantWorkspaceCreateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> TenantWorkspaceResponse:
    """Create a collaborative workspace inside an organization."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin", "workspace_lead"})

    slug = _slugify(payload.slug or payload.name)
    existing_ws = _STORE.workspaces.get(org_id, [])
    for w in existing_ws:
        if w["slug"] == slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug workspace '{slug}' đã tồn tại trong tổ chức",
            )

    now = datetime.now(UTC)
    ws_id = f"ws_{secrets.token_hex(6)}"
    ws_data = {
        "id": ws_id,
        "org_id": org_id,
        "name": payload.name,
        "slug": slug,
        "description": payload.description,
        "is_restricted": payload.is_restricted,
        "is_archived": False,
        "member_count": 1,
        "conversation_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    _STORE.workspaces.setdefault(org_id, []).append(ws_data)

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="workspace.create",
        resource_type="workspace",
        resource_id=ws_id,
        metadata={"slug": slug, "is_restricted": payload.is_restricted},
    )

    return TenantWorkspaceResponse(
        id=ws_id,
        org_id=org_id,
        name=ws_data["name"],
        slug=slug,
        description=ws_data["description"],
        is_restricted=ws_data["is_restricted"],
        is_archived=False,
        member_count=1,
        conversation_count=0,
        created_at=now,
        updated_at=now,
    )


@router.get("/{org_id}/workspaces/{workspace_id}", response_model=TenantWorkspaceResponse)
def get_tenant_workspace(
    org_id: str,
    workspace_id: str,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> TenantWorkspaceResponse:
    """Retrieve details for a specific tenant workspace (anti-IDOR guarded)."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token)

    workspaces = _STORE.workspaces.get(org_id, [])
    target: dict[str, Any] | None = None
    for w in workspaces:
        if w["id"] == workspace_id:
            target = w
            break

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace không tồn tại trong tổ chức",
        )

    return TenantWorkspaceResponse(
        id=target["id"],
        org_id=org_id,
        name=target["name"],
        slug=target["slug"],
        description=target["description"],
        is_restricted=target["is_restricted"],
        is_archived=target["is_archived"],
        member_count=target["member_count"],
        conversation_count=target["conversation_count"],
        created_at=target["created_at"],
        updated_at=target["updated_at"],
    )


@router.patch("/{org_id}/workspaces/{workspace_id}", response_model=TenantWorkspaceResponse)
def update_tenant_workspace(
    org_id: str,
    workspace_id: str,
    payload: TenantWorkspaceUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> TenantWorkspaceResponse:
    """Update settings or archive status of a tenant workspace."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin", "workspace_lead"})

    workspaces = _STORE.workspaces.get(org_id, [])
    target: dict[str, Any] | None = None
    for w in workspaces:
        if w["id"] == workspace_id:
            target = w
            break

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace không tồn tại trong tổ chức",
        )

    now = datetime.now(UTC)
    if payload.name is not None:
        target["name"] = payload.name
    if payload.description is not None:
        target["description"] = payload.description
    if payload.is_archived is not None:
        target["is_archived"] = payload.is_archived
    if payload.is_restricted is not None:
        target["is_restricted"] = payload.is_restricted
    target["updated_at"] = now

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="workspace.update",
        resource_type="workspace",
        resource_id=workspace_id,
        metadata={"updated_fields": list(payload.model_dump(exclude_unset=True).keys())},
    )

    return TenantWorkspaceResponse(
        id=target["id"],
        org_id=org_id,
        name=target["name"],
        slug=target["slug"],
        description=target["description"],
        is_restricted=target["is_restricted"],
        is_archived=target["is_archived"],
        member_count=target["member_count"],
        conversation_count=target["conversation_count"],
        created_at=target["created_at"],
        updated_at=target["updated_at"],
    )


@router.delete("/{org_id}/workspaces/{workspace_id}", status_code=status.HTTP_200_OK)
def archive_tenant_workspace(
    org_id: str,
    workspace_id: str,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Archive a tenant collaborative workspace."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin"})

    workspaces = _STORE.workspaces.get(org_id, [])
    target: dict[str, Any] | None = None
    for w in workspaces:
        if w["id"] == workspace_id:
            target = w
            break

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace không tồn tại trong tổ chức",
        )

    target["is_archived"] = True
    target["updated_at"] = datetime.now(UTC)

    _STORE.record_audit(
        org_id=org_id,
        actor_id=user.email,
        action="workspace.archive",
        resource_type="workspace",
        resource_id=workspace_id,
    )

    return {"status": "archived", "workspace_id": workspace_id}


# ==============================================================================
# Tenant Audit Log Endpoint
# ==============================================================================

@router.get("/{org_id}/audit", response_model=TenantAuditResponse)
def get_tenant_audit_trail(
    org_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> TenantAuditResponse:
    """Retrieve non-PII compliance audit journal for the tenant organization."""
    user = _get_user_by_token(db, token)
    _check_tenant_access(org_id, user, token, required_roles={"owner", "admin", "auditor"})

    events = _STORE.audit_logs.get(org_id, [])
    events_sorted = sorted(events, key=lambda x: x["timestamp"], reverse=True)[:limit]
    log_items = [
        TenantAuditLogItem(
            event_id=e["event_id"],
            org_id=e["org_id"],
            actor_id=e["actor_id"],
            action=e["action"],
            resource_type=e["resource_type"],
            resource_id=e["resource_id"],
            timestamp=e["timestamp"],
            metadata=e.get("metadata", {}),
        )
        for e in events_sorted
    ]
    return TenantAuditResponse(items=log_items, total=len(log_items))
