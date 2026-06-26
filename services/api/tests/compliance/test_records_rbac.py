"""RBAC + flag-gating tests for ``GET /compliance/records`` (task 7.2).

The admin compliance-records manifest (Req 6.1-6.4, 6.6) is reachable only by
the ``admin`` role and only when ``COMPLIANCE_RECORDS_ADMIN_ENABLED`` is on:

- a missing token is rejected with 401 (unauthenticated),
- a non-admin token (normal/researcher/doctor) is rejected with 403,
- an admin token with the flag **off** gets the inert ``{"enabled": false}``
  shape (flags-off baseline; Property P6),
- an admin token with the flag **on** gets the assembled manifest
  (``{"enabled": true, "records": {...}}``).

These exercise Correctness Property **P7** (RBAC on records) and the flag-off
equivalence guarantee at the endpoint layer.

**Validates: Requirements 6.6, 8.4**
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.core.security import create_access_token
from clara_api.main import app

client = TestClient(app)

RECORDS_PATH = "/api/v1/compliance/records"

ADMIN_EMAIL = "records-admin@compliance.clara"
NORMAL_EMAIL = "records-normal@compliance.clara"
RESEARCHER_EMAIL = "records-researcher@compliance.clara"
DOCTOR_EMAIL = "records-doctor@compliance.clara"


def _token(email: str, role: str) -> str:
    """Mint an access token directly.

    ``GET /compliance/records`` is gated by ``require_roles("admin")``, which
    inspects only the decoded JWT role (no DB lookup, no network), so minting a
    token here keeps the test hermetic and fast.
    """

    return create_access_token(subject=email, role=role)


def _set_records_flag(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    """Toggle ``COMPLIANCE_RECORDS_ADMIN_ENABLED`` on the cached settings.

    The endpoint reads the flag via ``Depends(get_settings)`` (a cached
    singleton); setting the attribute on it directly mirrors the established
    pattern for flag-gated endpoint tests in this suite.
    """

    monkeypatch.setattr(
        get_settings(), "compliance_records_admin_enabled", value, raising=False
    )


# ---------------------------------------------------------------------------
# RBAC (Property P7)
# ---------------------------------------------------------------------------


def test_records_requires_authentication(monkeypatch) -> None:
    # Even with the feature enabled, a missing token is rejected before the
    # handler runs.
    _set_records_flag(monkeypatch, True)
    response = client.get(RECORDS_PATH)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("email", "role"),
    [
        (NORMAL_EMAIL, "normal"),
        (RESEARCHER_EMAIL, "researcher"),
        (DOCTOR_EMAIL, "doctor"),
    ],
)
def test_records_forbidden_for_non_admin(monkeypatch, email: str, role: str) -> None:
    # Non-admin roles are RBAC-blocked with 403 regardless of the flag state.
    _set_records_flag(monkeypatch, True)
    token = _token(email, role)
    response = client.get(RECORDS_PATH, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Flag gating (Property P6 at the endpoint layer)
# ---------------------------------------------------------------------------


def test_records_flag_off_returns_disabled_shape(monkeypatch) -> None:
    # Admin, but the feature is off ⇒ inert "feature disabled" shape, no manifest.
    _set_records_flag(monkeypatch, False)
    token = _token(ADMIN_EMAIL, "admin")
    response = client.get(RECORDS_PATH, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_records_flag_on_returns_manifest_for_admin(monkeypatch) -> None:
    # Admin + feature on ⇒ the assembled, auditor-facing manifest.
    _set_records_flag(monkeypatch, True)
    token = _token(ADMIN_EMAIL, "admin")
    response = client.get(RECORDS_PATH, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    body = response.json()
    assert body["enabled"] is True
    records = body["records"]

    # The manifest is assembled from the source-of-truth artifacts (Req 6.1-6.4).
    assert records["ai_system_classification"]["classification"] == (
        "high-risk AI system (health domain)"
    )
    assert isinstance(records["documents"], list) and records["documents"]
    doc_ids = {doc["id"] for doc in records["documents"]}
    assert {"ropa", "risk_management_file", "dpia"}.issubset(doc_ids)
    # Live transfer registry + declared retention policy are included.
    assert isinstance(records["transfer_registry"], list)
    assert isinstance(records["retention_policy"], list) and records["retention_policy"]
