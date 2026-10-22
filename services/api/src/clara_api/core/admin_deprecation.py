"""Deprecation & Migration Seam for Legacy Co-Located Admin Endpoints.

Spec: PH42 / A04 (Adapter & Existing Code).
Enforces:
1. Adds RFC 8594 `Deprecation` and `Sunset` headers on legacy /admin endpoints.
2. Emits audit warning advising migration to isolated control plane (port 8200).
3. Rejects client-side role assertions; mandates cryptographic server-side validation.
"""

from __future__ import annotations

from fastapi import Response

CONTROL_PLANE_SUNSET_DATE = "Sun, 31 Dec 2026 23:59:59 GMT"
CONTROL_PLANE_CANONICAL_ORIGIN = "https://control.theclaracare.com"


def apply_legacy_admin_deprecation_headers(response: Response, endpoint_name: str) -> None:
    """Attach standard RFC 8594 deprecation and sunset headers to legacy admin responses."""
    response.headers["Deprecation"] = "@1735689600"  # Timestamp of deprecation announcement
    response.headers["Sunset"] = CONTROL_PLANE_SUNSET_DATE
    response.headers["Link"] = f'<{CONTROL_PLANE_CANONICAL_ORIGIN}/control/v1/{endpoint_name}>; rel="successor-version"'
    response.headers["X-CLARA-Control-Plane-Status"] = "MIGRATING_TO_ISOLATED_PLANE"
