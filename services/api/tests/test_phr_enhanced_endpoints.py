"""API-level tests for the PHR enhanced surface and flags-off equivalence.

Feature: personal-health-record
    Property 1  — Consent gate
    Property 10 — Audit is append-only and immutable
    Property 11 — Version snapshot monotonicity
    Property 12 — Access logging on non-owner / share reads
    Property 13 — Targeted update conservation
    Property 14 — OCR never auto-commits
    Property 16 — Share access control
    Property 21 — RBAC and owner-only access
    Property 22 — Flags-off legacy equivalence
    Req 19 — PHR sensitive data in DSAR export + deletion

These run against the real FastAPI app + SQLite session, mirroring the existing
``services/api/tests`` integration style. Feature flags are toggled via env +
``get_settings.cache_clear()`` (the same pattern the conftest uses).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.api.v1.endpoints.phr import _make_ocr_review_token
from clara_api.core.config import get_settings
from clara_api.db.models import PhrAudit, PhrProfile, PhrShare, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_PHR_ENV_KEYS = [
    "PHR_ENHANCED_ENABLED",
    "PHR_CONSENT_ENFORCEMENT_ENABLED",
    "PHR_RECONCILIATION_ENABLED",
    "PHR_ALLERGY_AWARE_DDI_ENABLED",
    "PHR_OCR_IMPORT_ENABLED",
    "PHR_OBSERVATIONS_ENABLED",
    "PHR_EXPORT_ENABLED",
    "PHR_SHARING_ENABLED",
    "PHR_REMINDERS_ENABLED",
    "PHR_COMPLETENESS_METER_ENABLED",
    "COMPLIANCE_DSAR_ENABLED",
]


def _enable(*env_keys: str) -> None:
    for key in env_keys:
        os.environ[key] = "true"
    get_settings.cache_clear()


def _disable_all() -> None:
    for key in _PHR_ENV_KEYS:
        os.environ.pop(key, None)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_phr_flags() -> Generator[None, None, None]:
    _disable_all()
    yield
    _disable_all()


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    status_response = client.get(
        "/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"}
    )
    required_version = status_response.json()["required_version"]
    client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ocr_review_token(email: str, candidate_ids: list[str]) -> str:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        return _make_ocr_review_token(user_id=user.id, candidate_ids=candidate_ids)


# ---------------------------------------------------------------------------
# Property 22 — flags-off legacy equivalence
# ---------------------------------------------------------------------------


def test_property22_record_shape_unchanged_with_flags_off() -> None:
    token = _login("phr-legacy@example.com")
    get_resp = client.get("/api/v1/phr/record", headers=_auth(token))
    assert get_resp.status_code == 200
    legacy_keys = {
        "full_name",
        "date_of_birth",
        "gender",
        "blood_type",
        "height_cm",
        "weight_kg",
        "phone",
        "address",
        "emergency_contact_name",
        "emergency_contact_phone",
        "insurance_id",
        "notes",
        "allergies",
        "conditions",
        "medications",
        "created_at",
        "updated_at",
    }
    assert set(get_resp.json().keys()) == legacy_keys


def test_property22_put_record_legacy_item_shape() -> None:
    token = _login("phr-legacy-put@example.com")
    resp = client.put(
        "/api/v1/phr/record",
        headers=_auth(token),
        json={
            "full_name": "Legacy User",
            "medications": [{"id": "x1", "name": "Panadol", "dose": "500mg"}],
        },
    )
    assert resp.status_code == 200
    med = resp.json()["medications"][0]
    # Legacy item shape only — no coded/provenance fields leak with flags off.
    assert set(med.keys()) == {
        "id",
        "name",
        "dose",
        "frequency",
        "started_on",
        "is_current",
        "note",
    }


def test_property22_enhanced_endpoints_404_with_flags_off() -> None:
    token = _login("phr-flagsoff@example.com")
    for path in ("/api/v1/phr/record/enhanced", "/api/v1/phr/history", "/api/v1/phr/consent"):
        resp = client.get(path, headers=_auth(token))
        assert resp.status_code == 404, path


def test_capabilities_reflects_master_and_sub() -> None:
    token = _login("phr-caps@example.com")
    # Sub-flag on but master off ⇒ effective off.
    _enable("PHR_RECONCILIATION_ENABLED")
    resp = client.get("/api/v1/phr/capabilities", headers=_auth(token))
    assert resp.status_code == 200
    flags = resp.json()["flags"]
    assert flags["enhanced"] is False
    assert flags["reconciliation"] is False

    _enable("PHR_ENHANCED_ENABLED", "PHR_RECONCILIATION_ENABLED")
    resp2 = client.get("/api/v1/phr/capabilities", headers=_auth(token))
    flags2 = resp2.json()["flags"]
    assert flags2["enhanced"] is True
    assert flags2["reconciliation"] is True


# ---------------------------------------------------------------------------
# Property 10/11/13 — entries: audit append-only, version monotonicity, targeted
# ---------------------------------------------------------------------------


def test_property13_entry_crud_audit_and_versions() -> None:
    _enable("PHR_ENHANCED_ENABLED")
    token = _login("phr-entries@example.com")

    # Create an allergy entry.
    create = client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin", "severity": "moderate"}},
    )
    assert create.status_code == 200
    allergies = create.json()["allergies"]
    assert len(allergies) == 1
    allergy = allergies[0]
    assert allergy["id"].startswith("srv_")  # server-assigned id
    assert allergy["is_coded"] is True
    assert allergy["information_source"] == "self-declared"
    assert allergy["verification_status"] == "unconfirmed"

    # Add a condition; the allergy must remain byte-for-byte (targeted, Prop 13).
    cond = client.post(
        "/api/v1/phr/entries/condition",
        headers=_auth(token),
        json={"fields": {"name": "Hypertension", "status": "active"}},
    )
    assert cond.status_code == 200
    assert cond.json()["allergies"][0] == allergy

    # Version monotonicity: current_version_no increased across changes.
    enhanced = client.get("/api/v1/phr/record/enhanced", headers=_auth(token))
    assert enhanced.json()["current_version_no"] >= 2

    history = client.get("/api/v1/phr/history", headers=_auth(token))
    versions = history.json()["versions"]
    version_nos = [v["version_no"] for v in versions]
    assert version_nos == sorted(version_nos, reverse=True)  # reverse-chronological
    assert version_nos[0] == max(version_nos)


def test_property10_audit_rows_are_appended_per_change() -> None:
    _enable("PHR_ENHANCED_ENABLED")
    token = _login("phr-audit@example.com")
    client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin"}},
    )
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == "phr-audit@example.com")).scalar_one()
        profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == user.id)).scalar_one()
        rows = list(db.execute(select(PhrAudit).where(PhrAudit.profile_id == profile.id)).scalars())
    assert len(rows) >= 1
    assert any(r.action == "create" and r.entity == "allergy" for r in rows)


def test_property5_endpoint_rejects_bad_severity() -> None:
    _enable("PHR_ENHANCED_ENABLED")
    token = _login("phr-validate@example.com")
    resp = client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin", "severity": "deadly"}},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Property 1 — consent gate (sharing)
# ---------------------------------------------------------------------------


def test_property1_share_requires_consent_when_enforced() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_SHARING_ENABLED", "PHR_CONSENT_ENFORCEMENT_ENABLED")
    token = _login("phr-share-consent@example.com")

    # No sharing consent yet ⇒ rejected with a descriptive precondition error.
    reject = client.post("/api/v1/phr/share", headers=_auth(token), json={"scope": "full"})
    assert reject.status_code == 428

    # Grant sharing consent, then it succeeds.
    grant = client.post(
        "/api/v1/phr/consent",
        headers=_auth(token),
        json={"purpose": "sharing", "granted": True},
    )
    assert grant.status_code == 200
    assert grant.json()["granted"] is True

    ok = client.post("/api/v1/phr/share", headers=_auth(token), json={"scope": "full"})
    assert ok.status_code == 200
    assert ok.json()["share_token"]


def test_property1_consent_revocation_takes_effect_next_request() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_SHARING_ENABLED", "PHR_CONSENT_ENFORCEMENT_ENABLED")
    token = _login("phr-revoke@example.com")
    client.post(
        "/api/v1/phr/consent", headers=_auth(token), json={"purpose": "sharing", "granted": True}
    )
    assert client.post("/api/v1/phr/share", headers=_auth(token), json={}).status_code == 200
    client.post(
        "/api/v1/phr/consent", headers=_auth(token), json={"purpose": "sharing", "granted": False}
    )
    assert client.post("/api/v1/phr/share", headers=_auth(token), json={}).status_code == 428


# ---------------------------------------------------------------------------
# Property 16 + 12 — share access control + access logging
# ---------------------------------------------------------------------------


def test_property16_share_read_revoke_and_access_log() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_SHARING_ENABLED")
    token = _login("phr-share-read@example.com")
    client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin"}},
    )
    created = client.post("/api/v1/phr/share", headers=_auth(token), json={"scope": "full"})
    share_token = created.json()["share_token"]
    with SessionLocal() as db:
        stored_share = db.execute(
            select(PhrShare).where(PhrShare.id == created.json()["share_id"])
        ).scalar_one()
        assert stored_share.token_hash == hashlib.sha256(share_token.encode()).hexdigest()
        assert not hasattr(stored_share, "share_token")

    # Public read works while active.
    read = client.get(f"/api/v1/phr/shared/{share_token}")
    assert read.status_code == 200
    assert read.json()["scope"] == "full"
    assert "hedge" in read.json()

    # Access logging on share read (Property 12).
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.email == "phr-share-read@example.com")
        ).scalar_one()
        profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == user.id)).scalar_one()
        share_reads = list(
            db.execute(
                select(PhrAudit).where(
                    PhrAudit.profile_id == profile.id, PhrAudit.action == "share_read"
                )
            ).scalars()
        )
    assert len(share_reads) >= 1

    # Revocation must not disclose an otherwise valid capability's lifecycle.
    client.delete(f"/api/v1/phr/share/{created.json()['share_id']}", headers=_auth(token))
    gone = client.get(f"/api/v1/phr/shared/{share_token}")
    assert gone.status_code == 404
    assert gone.json() == {"detail": {"code": "public_share_unavailable"}}


def test_property16_unknown_token_404() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_SHARING_ENABLED")
    resp = client.get("/api/v1/phr/shared/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Property 14 — OCR never auto-commits
# ---------------------------------------------------------------------------


def test_property14_ocr_confirm_required_to_commit() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_OCR_IMPORT_ENABLED")
    token = _login("phr-ocr@example.com")

    candidate_id = "ocr-review-panadol-001"
    # OCR candidates require an owner-bound review capability plus an explicit
    # per-row acknowledgement before the user-authored final value can write.
    confirm = client.post(
        "/api/v1/phr/import/ocr/confirm",
        headers=_auth(token),
        json={
            "review_token": _ocr_review_token("phr-ocr@example.com", [candidate_id]),
            "review_candidate_ids": [candidate_id],
            "medications": [
                {
                    "candidate_id": candidate_id,
                    "name": "Panadol",
                    "dose": "500mg",
                    "ocr_confidence": 0.95,
                    "confirmed": True,
                },
            ]
        },
    )
    assert confirm.status_code == 200
    meds = confirm.json()["medications"]
    assert len(meds) == 1
    assert meds[0]["information_source"] == "ocr"
    assert meds[0]["ocr_confidence"] == 0.95


def test_property14_ocr_confirm_blocks_low_confidence() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_OCR_IMPORT_ENABLED")
    token = _login("phr-ocr-block@example.com")
    candidate_id = "ocr-review-blurry-001"
    resp = client.post(
        "/api/v1/phr/import/ocr/confirm",
        headers=_auth(token),
        json={
            "review_token": _ocr_review_token("phr-ocr-block@example.com", [candidate_id]),
            "review_candidate_ids": [candidate_id],
            "medications": [
                {
                    "candidate_id": candidate_id,
                    "name": "blurry",
                    "requires_manual_confirm": True,
                    "ocr_confidence": 0.2,
                    "confirmed": False,
                }
            ]
        },
    )
    assert resp.status_code == 422


def test_property14_ocr_review_token_rejects_injected_candidate() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_OCR_IMPORT_ENABLED")
    email = "phr-ocr-token-bound@example.com"
    token = _login(email)
    reviewed_ids = ["ocr-review-bound-001", "ocr-review-bound-002"]
    response = client.post(
        "/api/v1/phr/import/ocr/confirm",
        headers=_auth(token),
        json={
            "review_token": _ocr_review_token(email, reviewed_ids),
            "review_candidate_ids": reviewed_ids,
            "medications": [
                {
                    "candidate_id": "ocr-review-injected-003",
                    "name": "Panadol",
                    "confirmed": True,
                }
            ],
        },
    )
    assert response.status_code == 422


def test_property14_ocr_review_token_fails_closed_when_malformed() -> None:
    """A corrupt review capability is rejected, never parsed into a 500 response."""

    _enable("PHR_ENHANCED_ENABLED", "PHR_OCR_IMPORT_ENABLED")
    token = _login("phr-ocr-token-malformed@example.com")
    candidate_id = "ocr-review-malformed-001"
    response = client.post(
        "/api/v1/phr/import/ocr/confirm",
        headers=_auth(token),
        json={
            "review_token": "not-a-valid.%%%token.signature",
            "review_candidate_ids": [candidate_id],
            "medications": [
                {
                    "candidate_id": candidate_id,
                    "name": "Panadol",
                    "confirmed": True,
                }
            ],
        },
    )
    assert response.status_code == 403


def test_phr_ocr_rejects_disguised_document_before_ocr_bridge() -> None:
    """The review-only OCR route still enforces the upload boundary first."""

    _enable("PHR_ENHANCED_ENABLED", "PHR_OCR_IMPORT_ENABLED")
    token = _login("phr-ocr-upload-safety@example.com")

    response = client.post(
        "/api/v1/phr/import/ocr/scan",
        headers=_auth(token),
        files={"file": ("receipt.pdf", b"not a PDF", "application/pdf")},
    )

    assert response.status_code == 415
    assert "khớp định dạng" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Property 21 — RBAC and owner-only access
# ---------------------------------------------------------------------------


def test_property21_phr_requires_auth() -> None:
    assert client.get("/api/v1/phr/record").status_code == 401


def test_property21_share_read_is_read_only() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_SHARING_ENABLED")
    token = _login("phr-readonly@example.com")
    created = client.post("/api/v1/phr/share", headers=_auth(token), json={"scope": "full"})
    share_token = created.json()["share_token"]
    # No write verb exists on the public share path.
    assert client.post(f"/api/v1/phr/shared/{share_token}").status_code == 405
    assert client.put(f"/api/v1/phr/shared/{share_token}").status_code == 405


# ---------------------------------------------------------------------------
# Observations + completeness + export
# ---------------------------------------------------------------------------


def test_observations_numeric_validation_and_listing() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_OBSERVATIONS_ENABLED")
    token = _login("phr-obs@example.com")
    bad = client.post(
        "/api/v1/phr/observations",
        headers=_auth(token),
        json={"name": "glucose", "value": "high", "unit": "mg/dL"},
    )
    assert bad.status_code == 422
    ok = client.post(
        "/api/v1/phr/observations",
        headers=_auth(token),
        json={"name": "glucose", "value": "5.4", "unit": "mmol/L"},
    )
    assert ok.status_code == 200
    listing = client.get("/api/v1/phr/observations", headers=_auth(token))
    assert len(listing.json()["observations"]) == 1


def test_export_is_downloadable_fhir_bundle() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_EXPORT_ENABLED")
    token = _login("phr-export@example.com")
    client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin"}},
    )
    resp = client.get("/api/v1/phr/export?resource=all", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/fhir+json")
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.json()["resourceType"] == "Bundle"


def test_completeness_meter_endpoint() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_COMPLETENESS_METER_ENABLED")
    token = _login("phr-complete@example.com")
    resp = client.get("/api/v1/phr/completeness", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["score"] <= 1.0
    assert "missing" in body
    # Telemetry projection carries no PII.
    assert "present_classes" in body["telemetry"]


# ---------------------------------------------------------------------------
# Req 19 — PHR in DSAR export + deletion
# ---------------------------------------------------------------------------


def test_req19_dsar_export_includes_phr_sensitive_data() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_OBSERVATIONS_ENABLED", "COMPLIANCE_DSAR_ENABLED")
    token = _login("phr-dsar@example.com")
    client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin"}},
    )
    client.post(
        "/api/v1/phr/observations",
        headers=_auth(token),
        json={"name": "glucose", "value": "5.4", "unit": "mmol/L"},
    )
    export = client.get("/api/v1/compliance/dsar/export", headers=_auth(token))
    assert export.status_code == 200
    bundle = export.json()["export"]
    assert bundle["data_classification"] == "sensitive_personal_data"
    assert bundle["phr_profile"]["allergies"]
    assert bundle["phr_observations"]
    assert bundle["phr_observations"][0]["name"] == "glucose"


def test_req19_deletion_anonymizes_phr() -> None:
    _enable("PHR_ENHANCED_ENABLED", "PHR_OBSERVATIONS_ENABLED")
    token = _login("phr-delete@example.com")
    client.post(
        "/api/v1/phr/entries/allergy",
        headers=_auth(token),
        json={"fields": {"name": "Penicillin"}},
    )
    from clara_api.compliance import dsar as dsar_service

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == "phr-delete@example.com")).scalar_one()
        dsar_service.fulfil_deletion(db, user=user)
        db.commit()
        profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == user.id)).scalar_one()
        assert profile.allergies_json == []
        assert profile.current_version_no == 0
