"""Tests for admin routers registration, platform analytics, privacy receipts, and visit verify/consent."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.core.security import create_access_token
from clara_api.db.models import LifeMapVisit, PhrProfile, PrivacyAuditReceipt, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _admin_token() -> str:
    settings = get_settings()
    return create_access_token(subject=settings.auth_bootstrap_admin_email, role="admin")


def _doctor_token() -> str:
    return create_access_token(subject="doctor@clara.test", role="doctor")


def _normal_token(email: str = "normal@clara.test") -> str:
    return create_access_token(subject=email, role="normal")


def _ensure_user_and_profile(email: str, role: str = "normal") -> tuple[User, PhrProfile]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, hashed_password="not-used", role=role, full_name="Test User")
            db.add(user)
            db.flush()
        else:
            user.role = role
            db.add(user)
            db.flush()

        profile = db.scalar(select(PhrProfile).where(PhrProfile.user_id == user.id))
        if profile is None:
            profile = PhrProfile(user_id=user.id, full_name=user.full_name or "Test User")
            db.add(profile)
            db.flush()
        db.commit()
        db.refresh(user)
        db.refresh(profile)
        return user, profile


# ---------------------------------------------------------------------------
# 1. Admin routers registration tests
# ---------------------------------------------------------------------------


def test_admin_users_router_registered() -> None:
    admin_tok = _admin_token()
    res = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data

    # Non-admin forbidden
    norm_tok = _normal_token()
    res_forbidden = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {norm_tok}"})
    assert res_forbidden.status_code == 403


def test_admin_experiments_router_registered() -> None:
    admin_tok = _admin_token()
    res = client.get("/api/v1/admin/experiments", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Non-admin forbidden
    norm_tok = _normal_token()
    res_forbidden = client.get("/api/v1/admin/experiments", headers={"Authorization": f"Bearer {norm_tok}"})
    assert res_forbidden.status_code == 403


def test_admin_feedback_router_registered() -> None:
    admin_tok = _admin_token()
    res = client.get("/api/v1/admin/feedback", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data

    # Non-admin forbidden
    norm_tok = _normal_token()
    res_forbidden = client.get("/api/v1/admin/feedback", headers={"Authorization": f"Bearer {norm_tok}"})
    assert res_forbidden.status_code == 403


# ---------------------------------------------------------------------------
# 2. Platform Analytics & Privacy Audit Receipts tests
# ---------------------------------------------------------------------------


def test_admin_platform_analytics_empty_reporting() -> None:
    admin_tok = _admin_token()
    res = client.get("/api/v1/admin/analytics/platform", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res.status_code == 200
    metrics = res.json()
    assert isinstance(metrics, list)
    assert len(metrics) >= 5

    # Check metric shape
    metric_ids = {m["metricId"] for m in metrics}
    assert "active_users" in metric_ids
    assert "queries_total" in metric_ids
    assert "api_requests_total" in metric_ids
    assert "api_error_rate_pct" in metric_ids

    for m in metrics:
        assert "metricId" in m
        assert "sampleSize" in m
        assert "windowStart" in m
        assert "windowEnd" in m
        assert "generatedAt" in m
        assert "freshnessState" in m

    # Non-admin forbidden
    norm_tok = _normal_token()
    res_forbidden = client.get("/api/v1/admin/analytics/platform", headers={"Authorization": f"Bearer {norm_tok}"})
    assert res_forbidden.status_code == 403


def test_admin_privacy_receipts_endpoint() -> None:
    admin_tok = _admin_token()

    with SessionLocal() as db:
        db.query(PrivacyAuditReceipt).delete()
        db.commit()

    # Empty list when no receipts exist (never fabricating pass receipts)
    res = client.get("/api/v1/admin/privacy-receipts", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res.status_code == 200
    assert res.json() == []

    # Insert a receipt and verify retrieval
    with SessionLocal() as db:
        receipt = PrivacyAuditReceipt(
            audit_id="audit-test-001",
            scanner_version="v2.1",
            scope_digest="sha256:abcd",
            result="pass",
            finding_count=0,
            artifact_digest="sha256:1234",
            executed_at=datetime.now(timezone.utc),
        )
        db.add(receipt)
        db.commit()

    res2 = client.get("/api/v1/admin/privacy-receipts", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res2.status_code == 200
    data = res2.json()
    assert len(data) == 1
    assert data[0]["auditId"] == "audit-test-001"
    assert data[0]["scannerVersion"] == "v2.1"
    assert data[0]["result"] == "pass"
    assert data[0]["findingCount"] == 0

    # Non-admin forbidden
    norm_tok = _normal_token()
    res_forbidden = client.get("/api/v1/admin/privacy-receipts", headers={"Authorization": f"Bearer {norm_tok}"})
    assert res_forbidden.status_code == 403


# ---------------------------------------------------------------------------
# 3. Visit Verify and Scribe Consent tests
# ---------------------------------------------------------------------------


def test_visit_verify_and_scribe_consent() -> None:
    patient_email = "patient-visit@clara.test"
    doctor_email = "doctor-visit@doctor.clara"
    _ensure_user_and_profile(patient_email, role="normal")
    _ensure_user_and_profile(doctor_email, role="doctor")

    patient_tok = _normal_token(patient_email)
    doctor_tok = create_access_token(subject=doctor_email, role="doctor")
    admin_tok = _admin_token()

    # Create visit as patient
    create_res = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {patient_tok}"},
        json={"title": "Cardiology Consultation", "goal": "Check blood pressure", "visit_type": "consultation"},
    )
    assert create_res.status_code == 201
    visit_data = create_res.json()
    visit_id = visit_data["id"]
    assert visit_data["status"] == "planning"

    # 1. Update scribe consent (grant)
    grant_res = client.patch(
        f"/api/v1/visits/{visit_id}/scribe-consent",
        headers={"Authorization": f"Bearer {patient_tok}"},
        json={"granted": True, "policy_version": "visit-scribe-v2"},
    )
    assert grant_res.status_code == 200
    assert grant_res.json()["status"] == "granted"
    assert grant_res.json()["policy_version"] == "visit-scribe-v2"

    # 2. Update scribe consent (revoke)
    revoke_res = client.patch(
        f"/api/v1/visits/{visit_id}/scribe-consent",
        headers={"Authorization": f"Bearer {patient_tok}"},
        json={"granted": False, "reason": "Patient requested privacy"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"
    assert revoke_res.json()["revoked"] is True

    # 3. Verify visit as non-doctor (patient) -> 403 Forbidden
    verify_forbidden = client.post(
        f"/api/v1/visits/{visit_id}/verify",
        headers={"Authorization": f"Bearer {patient_tok}"},
        json={"notes": "Normal user attempting verification"},
    )
    assert verify_forbidden.status_code == 403

    # 4. Verify visit as doctor -> 200 OK with signature_digest
    verify_res = client.post(
        f"/api/v1/visits/{visit_id}/verify",
        headers={"Authorization": f"Bearer {doctor_tok}"},
        json={"notes": "Doctor verified consultation records."},
    )
    assert verify_res.status_code == 200
    verified_data = verify_res.json()
    assert verified_data["status"] == "verified"
    assert "signature_digest" in verified_data
    assert len(verified_data["signature_digest"]) == 64
    assert verified_data["id"] == visit_id

    # 5. Verify visit as admin on non-existent visit -> 404
    missing_res = client.post(
        "/api/v1/visits/non-existent-id/verify",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert missing_res.status_code == 404
