"""Normalization status + low-confidence OCR confirm-gate surfacing.

Feature: clara-selfmed-careguard-upgrade (task 3.3)

Pins Requirements 2.1, 2.2, 2.5, 2.6:

* Cabinet item responses surface a derived ``normalization_status``
  (matched / candidate / fallback / needs_review) plus a convenience
  ``needs_review`` boolean, derived from the existing ``normalization_source`` +
  ``normalization_confidence`` (Req 2.1, 2.6).
* A medicine that cannot be confidently normalized is **retained** (never
  dropped) and flagged ``needs_review`` (Req 2.5).
* The low-confidence OCR manual-confirm gate is preserved and its state is
  surfaced on scan responses via ``confirm_gate`` and per-detection
  ``normalization_status`` (Req 2.2, 2.6).

These additions are additive + nullable, so flags-off byte-equivalence of the
pre-existing response fields is preserved (design Property P12).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints.careguard import (
    LOW_CONFIDENCE_OCR_THRESHOLD,
    _derive_normalization_status,
)
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Pure derivation (Req 2.1, 2.5, 2.6)
# ---------------------------------------------------------------------------


def test_derive_status_maps_each_source() -> None:
    # Exact dictionary hit.
    assert _derive_normalization_status("db", 1.0) == "matched"
    # Fuzzy dictionary candidate (>= 0.78 by construction).
    assert _derive_normalization_status("candidate", 0.81) == "candidate"
    # Alias-map hit (brand -> a different canonical), confidence 0.72.
    assert _derive_normalization_status("fallback", 0.72) == "fallback"


def test_derive_status_low_confidence_is_needs_review() -> None:
    # Unmatched / exact-canonical-with-no-db-mapping fallback (0.35) is below the
    # review threshold and must surface as needs_review (Req 2.5).
    assert _derive_normalization_status("fallback", 0.35) == "needs_review"
    # Any source below the threshold is treated as needs_review.
    assert _derive_normalization_status("candidate", 0.10) == "needs_review"


def test_derive_status_none_source_is_unknown() -> None:
    assert _derive_normalization_status(None, None) is None


# ---------------------------------------------------------------------------
# Cabinet responses (Req 2.1, 2.5, 2.6)
# ---------------------------------------------------------------------------


def test_unmatched_name_retained_and_flagged_needs_review() -> None:
    token = _login("needs-review@example.com")
    unknown_name = "Khôngcóthuốcnày Zxq"

    created = client.post(
        "/api/v1/careguard/cabinet/items",
        headers=_auth(token),
        json={"drug_name": unknown_name, "source": "manual"},
    )
    assert created.status_code == 200
    body = created.json()
    # Retained, not dropped (Req 2.5): the user-entered name is preserved.
    assert body["drug_name"] == unknown_name
    assert body["normalization_status"] == "needs_review"
    assert body["needs_review"] is True

    # Still present (and still flagged) on a subsequent read.
    listing = client.get("/api/v1/careguard/cabinet", headers=_auth(token))
    assert listing.status_code == 200
    items = {item["id"]: item for item in listing.json()["items"]}
    assert items[body["id"]]["drug_name"] == unknown_name
    assert items[body["id"]]["needs_review"] is True


def test_brand_alias_resolves_to_fallback_status() -> None:
    token = _login("alias-fallback@example.com")
    # A known brand alias maps to a different canonical ingredient -> fallback.
    created = client.post(
        "/api/v1/careguard/cabinet/items",
        headers=_auth(token),
        json={"drug_name": "Panadol", "source": "manual"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["normalization_source"] == "fallback"
    assert body["normalization_status"] == "fallback"
    assert body["needs_review"] is False


# ---------------------------------------------------------------------------
# OCR confirm-gate surfacing (Req 2.2, 2.6)
# ---------------------------------------------------------------------------


def test_scan_text_surfaces_confirm_gate_and_detection_status() -> None:
    token = _login("confirm-gate@example.com")
    response = client.post(
        "/api/v1/careguard/cabinet/scan-text",
        headers=_auth(token),
        json={"text": "Toa thuoc: Panadol 500mg uong sang"},
    )
    assert response.status_code == 200
    body = response.json()

    detections = body["detections"]
    assert detections, "expected at least one detection from the prescription text"
    # Every detection carries the derived normalization status.
    for detection in detections:
        assert "normalization_status" in detection

    gate = body["confirm_gate"]
    assert gate is not None
    assert gate["threshold"] == LOW_CONFIDENCE_OCR_THRESHOLD
    assert gate["total_detections"] == len(detections)
    # The "Panadol" detection is below the OCR threshold, so the gate reports at
    # least one detection requiring manual confirmation (Req 2.2).
    assert gate["requires_confirmation"] >= 1
    assert 0 <= gate["confirmed"] <= gate["total_detections"]
    assert gate["needs_review"] >= 0
