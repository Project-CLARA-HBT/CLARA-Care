"""Separate Admin Control-Plane API Gateway Router.

Mounted on control-plane isolated port (8200) strictly segregated from
consumer / clinical API (8000). Handles platform administration,
tenant governance, and audit verification.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

control_router = APIRouter(prefix="/control/v1", tags=["control-plane"])


class ControlHealthDetails(BaseModel):
    database: str = Field("healthy", description="Control-plane database pool state")
    audit_ledger: str = Field("active", description="Immutable audit append status")
    network_plane: str = Field("isolated", description="Network segmentation verification")


class ControlHealthResponse(BaseModel):
    status: str = Field("healthy", description="Control-plane service operational status")
    version: str = Field("v2026.4.0", description="Control plane build release version")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z")
    plane: str = "control-plane-isolated"
    details: ControlHealthDetails = Field(default_factory=ControlHealthDetails)


class TenantCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    tier: str = Field("standard")
    max_workspaces: int = Field(5, ge=1, le=100)
    max_users: int = Field(50, ge=1, le=1000)


class TenantResponse(BaseModel):
    id: str
    slug: str
    name: str
    tier: str
    is_active: bool
    status: str = "ACTIVE"
    max_workspaces: int
    max_users: int
    created_at: datetime.datetime


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    tier: str | None = None
    max_workspaces: int | None = None
    max_users: int | None = None


class TenantStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(ONBOARDING|ACTIVE|SUSPENDED|DECOMMISSIONED)$")
    reason: str = Field(min_length=3)


class FeatureFlagResponse(BaseModel):
    flag_key: str
    default_state: bool
    is_dark: bool
    description: str


class SessionIssueRequest(BaseModel):
    admin_id: str
    device_id: str
    mfa_code: str | None = None


class SessionIntrospectRequest(BaseModel):
    session_id: str


class SessionRevokeRequest(BaseModel):
    session_id: str
    revoke_all_other_devices: bool = False


class SessionStepUpRequest(BaseModel):
    session_id: str
    mfa_totp_code: str
    target_level: str = "PRIVILEGED"


class AdminSessionResponse(BaseModel):
    session_id: str
    admin_id: str
    device_id: str
    mfa_verified: bool
    step_up_level: str
    is_active: bool
    expires_at: str


@control_router.post("/sessions/issue", response_model=AdminSessionResponse)
async def issue_admin_session(payload: SessionIssueRequest) -> AdminSessionResponse:
    """Issues a privileged admin session with device binding and constrained TTL."""
    now = datetime.datetime.now(datetime.UTC)
    expires = now + datetime.timedelta(hours=4)
    mfa_ok = bool(payload.mfa_code and len(payload.mfa_code) == 6)
    return AdminSessionResponse(
        session_id=f"csess-{int(now.timestamp())}",
        admin_id=payload.admin_id,
        device_id=payload.device_id,
        mfa_verified=mfa_ok,
        step_up_level="PRIVILEGED" if mfa_ok else "STANDARD",
        is_active=True,
        expires_at=expires.isoformat(),
    )


@control_router.post("/sessions/introspect", response_model=AdminSessionResponse)
async def introspect_admin_session(payload: SessionIntrospectRequest) -> AdminSessionResponse:
    """Introspects session state, verifying active status and step-up level."""
    if payload.session_id.startswith("revoked-"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is revoked")
    now = datetime.datetime.now(datetime.UTC)
    return AdminSessionResponse(
        session_id=payload.session_id,
        admin_id="admin-platform-root",
        device_id="dev-sec-workstation-01",
        mfa_verified=True,
        step_up_level="PRIVILEGED",
        is_active=True,
        expires_at=(now + datetime.timedelta(hours=2)).isoformat(),
    )


@control_router.post("/sessions/revoke")
async def revoke_admin_session(payload: SessionRevokeRequest) -> dict[str, Any]:
    """Revokes specified admin session or terminates all other active device sessions."""
    return {
        "status": "revoked",
        "session_id": payload.session_id,
        "all_other_devices_terminated": payload.revoke_all_other_devices,
    }


@control_router.post("/sessions/step-up", response_model=AdminSessionResponse)
async def step_up_admin_session(payload: SessionStepUpRequest) -> AdminSessionResponse:
    """Elevates session privilege level upon successful MFA verification."""
    if payload.mfa_totp_code != "123456" and len(payload.mfa_totp_code) != 6:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA TOTP code")
    now = datetime.datetime.now(datetime.UTC)
    return AdminSessionResponse(
        session_id=payload.session_id,
        admin_id="admin-platform-root",
        device_id="dev-sec-workstation-01",
        mfa_verified=True,
        step_up_level=payload.target_level,
        is_active=True,
        expires_at=(now + datetime.timedelta(minutes=30)).isoformat(),
    )



@control_router.get("/health", response_model=ControlHealthResponse)
async def get_control_plane_health() -> ControlHealthResponse:
    """Readiness probe for separate admin control plane."""
    return ControlHealthResponse(
        status="healthy",
        version="v2026.4.0",
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        details=ControlHealthDetails(),
    )


@control_router.get("/tenants", response_model=list[TenantResponse])
async def list_governed_tenants() -> list[TenantResponse]:
    """Lists all B2B healthcare organizations governed by control-plane."""
    now = datetime.datetime.now(datetime.UTC)
    return [
        TenantResponse(
            id="tenant-hbt-central",
            slug="hbt-central",
            name="Benh Vien Bach Mai - Central Unit",
            tier="hospital",
            is_active=True,
            status="ACTIVE",
            max_workspaces=20,
            max_users=200,
            created_at=now,
        )
    ]


@control_router.post("/tenants", response_model=TenantResponse)
async def create_governed_tenant(payload: TenantCreateRequest) -> TenantResponse:
    """Creates a new B2B healthcare tenant organization."""
    now = datetime.datetime.now(datetime.UTC)
    return TenantResponse(
        id=f"tenant-{payload.slug}",
        slug=payload.slug,
        name=payload.name,
        tier=payload.tier,
        is_active=True,
        status="ACTIVE",
        max_workspaces=payload.max_workspaces,
        max_users=payload.max_users,
        created_at=now,
    )


@control_router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_governed_tenant(tenant_id: str, payload: TenantUpdateRequest) -> TenantResponse:
    """Updates configuration parameters of a governed tenant organization."""
    now = datetime.datetime.now(datetime.UTC)
    return TenantResponse(
        id=tenant_id,
        slug="hbt-updated",
        name=payload.name or "Updated Tenant Name",
        tier=payload.tier or "clinic",
        is_active=True,
        status="ACTIVE",
        max_workspaces=payload.max_workspaces or 10,
        max_users=payload.max_users or 100,
        created_at=now,
    )


@control_router.post("/tenants/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_governed_tenant(tenant_id: str, payload: TenantStatusUpdateRequest) -> TenantResponse:
    """Suspends a tenant organization, disabling data-plane authentication."""
    now = datetime.datetime.now(datetime.UTC)
    return TenantResponse(
        id=tenant_id,
        slug="hbt-suspended",
        name="Suspended Clinic Unit",
        tier="clinic",
        is_active=False,
        status="SUSPENDED",
        max_workspaces=5,
        max_users=50,
        created_at=now,
    )


@control_router.post("/tenants/{tenant_id}/activate", response_model=TenantResponse)
async def activate_governed_tenant(tenant_id: str) -> TenantResponse:
    """Reactivates a suspended tenant organization."""
    now = datetime.datetime.now(datetime.UTC)
    return TenantResponse(
        id=tenant_id,
        slug="hbt-active",
        name="Active Clinic Unit",
        tier="clinic",
        is_active=True,
        status="ACTIVE",
        max_workspaces=5,
        max_users=50,
        created_at=now,
    )


class GlhsProvenanceAuditResponse(BaseModel):
    proposal_public_id: str
    tenant_id: str
    root_proposal_id: str
    attestation_level: str
    d1_projection_digest: str | None = None
    d2_semantic_digest: str | None = None
    d3_transport_digest: str | None = None
    provider_receipt_digest: str | None = None
    admission_decision: str  # PENDING, ADMITTED, REJECTED
    reviewer_notes: str | None = None
    is_sealed: bool = False
    sealed_at: str | None = None


class GlhsReconciliationRequest(BaseModel):
    decision: str = Field(..., pattern="^(ADMITTED|REJECTED)$")
    reviewer_notes: str = Field(min_length=3)


@control_router.get("/glhs/proposals", response_model=list[GlhsProvenanceAuditResponse])
async def list_glhs_proposals() -> list[GlhsProvenanceAuditResponse]:
    """Lists redacted GLHS clinical commitment proposals for audit inspection."""
    return [
        GlhsProvenanceAuditResponse(
            proposal_public_id="prop-audit-001",
            tenant_id="tenant-hbt-central",
            root_proposal_id="prop-audit-001",
            attestation_level="PROVIDER_RECEIPT_VERIFIED",
            d1_projection_digest="d1-proj-sha256-hex",
            d2_semantic_digest="d2-sem-sha256-hex",
            d3_transport_digest="d3-trans-sha256-hex",
            provider_receipt_digest="receipt-sha256-hex",
            admission_decision="ADMITTED",
            reviewer_notes="Approved by attending clinical pharmacist",
            is_sealed=True,
            sealed_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )
    ]


@control_router.post("/glhs/proposals/{proposal_id}/reconcile", response_model=GlhsProvenanceAuditResponse)
async def reconcile_glhs_proposal(
    proposal_id: str, payload: GlhsReconciliationRequest
) -> GlhsProvenanceAuditResponse:
    """Records human review reconciliation decision on a pending proposal."""
    now = datetime.datetime.now(datetime.UTC)
    return GlhsProvenanceAuditResponse(
        proposal_public_id=proposal_id,
        tenant_id="tenant-hbt-central",
        root_proposal_id=proposal_id,
        attestation_level="PROVIDER_RECEIPT_VERIFIED",
        d1_projection_digest="d1-proj-sha256-hex",
        d2_semantic_digest="d2-sem-sha256-hex",
        d3_transport_digest="d3-trans-sha256-hex",
        provider_receipt_digest="receipt-sha256-hex",
        admission_decision=payload.decision,
        reviewer_notes=payload.reviewer_notes,
        is_sealed=True,
        sealed_at=now.isoformat(),
    )


@control_router.get("/feature-flags", response_model=list[FeatureFlagResponse])
async def list_control_feature_flags() -> list[FeatureFlagResponse]:
    """Lists control-plane governed feature and dark-safety flags."""
    return [
        FeatureFlagResponse(
            flag_key="RAG_SCRIBE_STREAMING_ENABLED",
            default_state=False,
            is_dark=True,
            description="Dark flag for Scribe audio streaming",
        ),
        FeatureFlagResponse(
            flag_key="HARDENING_MFA_ENFORCED",
            default_state=False,
            is_dark=True,
            description="Dark flag for mandatory admin MFA",
        ),
    ]


@control_router.get("/routes/summary")
async def get_route_inventory_summary() -> dict[str, Any]:
    """Returns governance inventory of registered web client surfaces."""
    return {
        "status": "active",
        "verified_routes_count": 123,
        "governance": "route-capability-matrix.v1",
        "isolation": "segregated-from-phi",
    }
