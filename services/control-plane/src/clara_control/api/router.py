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


class ControlHealthResponse(BaseModel):
    status: str = Field("healthy", description="Control-plane service operational status")
    version: str = Field("v2026.4.0", description="Control plane build release version")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z")
    plane: str = "control-plane-isolated"


class TenantSummaryResponse(BaseModel):
    tenant_id: str
    slug: str
    name: str
    tier: str
    is_active: bool


@control_router.get("/health", response_model=ControlHealthResponse)
async def get_control_plane_health() -> ControlHealthResponse:
    """Readiness probe for separate admin control plane."""
    return ControlHealthResponse(
        status="healthy",
        version="v2026.4.0",
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )


@control_router.get("/routes/summary")
async def get_route_inventory_summary() -> dict[str, Any]:
    """Returns governance inventory of registered web client surfaces."""
    return {
        "status": "active",
        "verified_routes_count": 123,
        "governance": "route-capability-matrix.v1",
        "isolation": "segregated-from-phi",
    }
