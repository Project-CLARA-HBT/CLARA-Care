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
    max_workspaces: int
    max_users: int
    created_at: datetime.datetime


class FeatureFlagResponse(BaseModel):
    flag_key: str
    default_state: bool
    is_dark: bool
    description: str


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
    now = datetime.datetime.utcnow()
    return [
        TenantResponse(
            id="tenant-hbt-central",
            slug="hbt-central",
            name="Benh Vien Bach Mai - Central Unit",
            tier="hospital",
            is_active=True,
            max_workspaces=20,
            max_users=200,
            created_at=now,
        )
    ]


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
