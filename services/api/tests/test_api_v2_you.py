"""Unit and integration tests for CLARA API v2 You, Privacy, Sharing, and Integrations.

Covers:
- `GET /api/v2/you/profile`: personal details, emergency card data, preferences.
- `GET /api/v2/you/sharing`: active access grants, family invitations, access logs.
- `POST /api/v2/you/sharing/grants`: create granular access grant.
- `DELETE /api/v2/you/sharing/grants/{grant_id}`: server-authoritative revocation.
- `GET /api/v2/you/privacy`: consent status, AI usage disclosure, DSAR tools.
- `GET /api/v2/you/integrations`: list connected health data sources and status.
- `POST /api/v2/you/integrations/sync`: receive canonical connected health envelope.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.compliance.redaction import hash_user_ref
from clara_api.core.security import create_access_token
from clara_api.db.models import (
    ConnectorAccount,
    DsarRequest,
    PhrProfile,
    User,
    UserConsent,
    WearableObservation,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


def _create_user(db: Session, label: str = "you-user", role: str = "normal") -> User:
    suffix = uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@clara.vn",
        hashed_password="test-password-hash",
        role=role,
        is_email_verified=True,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(
    db: Session,
    user: User,
    *,
    full_name: str = "Nguyễn Văn Bạn",
    blood_type: str = "O+",
    allergies: list[dict] | None = None,
    medications: list[dict] | None = None,
    conditions: list[dict] | None = None,
    emergency_prefs: dict | None = None,
) -> PhrProfile:
    profile = PhrProfile(
        user_id=user.id,
        full_name=full_name,
        date_of_birth=date(1990, 5, 15),
        gender="male",
        blood_type=blood_type,
        height_cm=175.0,
        weight_kg=70.5,
        phone="0901234567",
        contact_email=user.email,
        address="123 Nguyễn Huệ, Q1, TP.HCM",
        emergency_contact_name="Trần Thị Người Thân",
        emergency_contact_phone="0909876543",
        emergency_contact_relationship="Spouse",
        emergency_contact_note="Gọi khi khẩn cấp",
        insurance_provider="Bảo Việt Health Care",
        insurance_id="BV-99887766",
        insurance_expiry=date(2027, 12, 31),
        allergy_status="known_allergies",
        notes="Tiền sử dị ứng penicillin nhẹ",
        allergies_json=allergies
        or [{"name": "Penicillin", "severity": "mild", "reaction": "Phát ban"}],
        medications_json=medications
        or [{"name": "Amlodipine 5mg", "dose": "1 viên/ngày", "is_current": True}],
        conditions_json=conditions
        or [{"name": "Tăng huyết áp", "status": "active"}],
        emergency_card_prefs_json=emergency_prefs
        or {
            "allergies": True,
            "current_medications": True,
            "conditions": True,
            "blood_type": True,
            "emergency_contact": True,
        },
        onboarding_status="completed",
        current_version_no=1,
        status="active",
        locale="vi",
        timezone="Asia/Ho_Chi_Minh",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _auth_headers(user: User, profile: PhrProfile | None = None) -> dict[str, str]:
    token = create_access_token(subject=user.email, role=user.role)
    headers = {"Authorization": f"Bearer {token}"}
    if profile:
        headers["X-CLARA-Profile-Context"] = profile.public_id
    return headers


# ---------------------------------------------------------------------------
# 1. Profile & Emergency Card Endpoint Tests
# ---------------------------------------------------------------------------


def test_get_you_profile_success() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="profile-user")
        profile = _create_profile(db, user)

        headers = _auth_headers(user, profile)
        response = client.get("/api/v2/you/profile", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert "data" in payload
        data = payload["data"]

        assert data["full_name"] == "Nguyễn Văn Bạn"
        assert data["blood_type"] == "O+"
        assert data["height_cm"] == 175.0
        assert data["weight_kg"] == 70.5
        assert data["phone"] == "0901234567"
        assert data["insurance_provider"] == "Bảo Việt Health Care"

        # Check emergency card projection
        emergency_card = data["emergency_card"]
        assert emergency_card["blood_type"] == "O+"
        assert len(emergency_card["allergies"]) == 1
        assert emergency_card["allergies"][0]["name"] == "Penicillin"
        assert len(emergency_card["current_medications"]) == 1
        assert emergency_card["current_medications"][0]["name"] == "Amlodipine 5mg"
        assert len(emergency_card["conditions"]) == 1
        assert emergency_card["conditions"][0]["name"] == "Tăng huyết áp"
        assert emergency_card["emergency_contact"]["name"] == "Trần Thị Người Thân"
        assert "disclaimer" in emergency_card
        assert "vi" in emergency_card["disclaimer"]

        # Check preferences
        prefs = data["preferences"]
        assert prefs["locale"] == "vi"
        assert prefs["timezone"] == "Asia/Ho_Chi_Minh"
        assert prefs["emergency_card_prefs"]["allergies"] is True
    finally:
        db.close()


def test_get_you_profile_unauthorized() -> None:
    response = client.get("/api/v2/you/profile")
    assert response.status_code in {401, 403}


# ---------------------------------------------------------------------------
# 2. Sharing & Family Circle Tests
# ---------------------------------------------------------------------------


def test_get_you_sharing_overview_empty() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="sharing-empty")
        profile = _create_profile(db, user)

        headers = _auth_headers(user, profile)
        response = client.get("/api/v2/you/sharing", headers=headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["grants"] == []
        assert data["invitations"] == []
        assert data["total_active_grants"] == 0
        assert data["total_pending_invitations"] == 0
    finally:
        db.close()


def test_create_and_revoke_sharing_grant() -> None:
    db = SessionLocal()
    try:
        owner = _create_user(db, label="grant-owner")
        profile = _create_profile(db, owner)
        grantee = _create_user(db, label="grant-recipient")

        headers = _auth_headers(owner, profile)

        # 1. Create a granular access grant
        grant_req = {
            "target_email": grantee.email,
            "data_classes": ["profile", "medications", "vitals"],
            "allowed_actions": ["view"],
            "purpose": "caregiving",
            "duration_days": 14,
        }
        create_resp = client.post(
            "/api/v2/you/sharing/grants",
            json=grant_req,
            headers=headers,
        )
        assert create_resp.status_code == 201
        created_data = create_resp.json()["data"]
        public_id = created_data["public_id"]

        assert created_data["grantee_email"] == grantee.email
        assert created_data["purpose"] == "caregiving"
        assert created_data["status"] == "active"
        assert set(created_data["data_classes"]) == {"profile", "medications", "vitals"}

        # 2. Verify grant appears in sharing overview
        overview_resp = client.get("/api/v2/you/sharing", headers=headers)
        assert overview_resp.status_code == 200
        overview_data = overview_resp.json()["data"]
        assert overview_data["total_active_grants"] == 1
        assert len(overview_data["grants"]) == 1
        assert len(overview_data["access_logs"]) >= 1

        # 3. Revoke the grant
        revoke_resp = client.delete(
            f"/api/v2/you/sharing/grants/{public_id}?reason=caregiver_changed",
            headers=headers,
        )
        assert revoke_resp.status_code == 200
        revoke_data = revoke_resp.json()["data"]
        assert revoke_data["revoked"] is True
        assert revoke_data["status"] == "revoked"

        # 4. Verify grant is now marked as revoked
        overview_after = client.get("/api/v2/you/sharing", headers=headers).json()["data"]
        assert overview_after["total_active_grants"] == 0
        assert overview_after["grants"][0]["status"] == "revoked"
    finally:
        db.close()


def test_create_grant_invalid_grantee() -> None:
    db = SessionLocal()
    try:
        owner = _create_user(db, label="grant-invalid")
        profile = _create_profile(db, owner)
        headers = _auth_headers(owner, profile)

        # Missing target_email and target_user_id
        resp = client.post(
            "/api/v2/you/sharing/grants",
            json={"data_classes": ["profile"], "purpose": "family"},
            headers=headers,
        )
        assert resp.status_code == 422
    finally:
        db.close()


def test_revoke_nonexistent_grant_returns_404() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="revoke-404")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        resp = client.delete(
            "/api/v2/you/sharing/grants/nonexistent-grant-id",
            headers=headers,
        )
        assert resp.status_code == 404
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Privacy & DSAR Hub Tests
# ---------------------------------------------------------------------------


def test_get_you_privacy_hub() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="privacy-user")
        profile = _create_profile(db, user)

        # Seed a consent record
        consent = UserConsent(
            user_id=user.id,
            consent_type="medical_disclaimer",
            consent_version="2026-08-01",
            accepted_at=datetime.now(UTC),
        )
        db.add(consent)

        # Seed a DSAR request
        dsar = DsarRequest(
            user_ref=hash_user_ref(user.id),
            kind="export",
            status="received",
            created_at=datetime.now(UTC),
            due_at=datetime.now(UTC) + timedelta(days=30),
        )
        db.add(dsar)
        db.commit()

        headers = _auth_headers(user, profile)
        response = client.get("/api/v2/you/privacy", headers=headers)

        assert response.status_code == 200
        data = response.json()["data"]

        # Check consents
        consents = data["consents"]
        assert len(consents) >= 4
        med_disclaimer = next(c for c in consents if c["consent_type"] == "medical_disclaimer")
        assert med_disclaimer["is_active"] is True
        assert med_disclaimer["consent_version"] == "2026-08-01"

        # Check AI disclosure
        ai_disc = data["ai_usage_disclosure"]
        assert "FIDES" in ai_disc["framework"]
        assert len(ai_disc["governance_principles"]) >= 3
        assert ai_disc["emergency_override_enabled"] is True
        assert "CLARA" in ai_disc["summary_vi"]

        # Check DSAR entry points
        dsar_data = data["dsar"]
        assert dsar_data["export_endpoint"] == "/api/v1/compliance/dsar/export"
        assert dsar_data["delete_endpoint"] == "/api/v1/compliance/dsar/requests"
        assert dsar_data["statutory_window_days"] == 30
        assert len(dsar_data["active_requests"]) == 1
        assert dsar_data["active_requests"][0]["kind"] == "export"
        assert dsar_data["active_requests"][0]["status"] == "received"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Connected Health & Integrations Tests
# ---------------------------------------------------------------------------


def test_get_you_integrations_list() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="integrations-user")
        profile = _create_profile(db, user)

        # Seed an active Health Connect integration
        conn = ConnectorAccount(
            user_id=user.id,
            profile_id=profile.id,
            provider="health_connect",
            display_label="Android Health Connect",
            status="connected",
            data_types_json=["steps", "heart_rate", "sleep"],
            last_synced_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db.add(conn)
        db.commit()

        headers = _auth_headers(user, profile)
        response = client.get("/api/v2/you/integrations", headers=headers)

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["connected_count"] == 1
        assert data["available_count"] >= 5
        assert data["last_sync_overall"] is not None

        hc_item = next(i for i in data["integrations"] if i["provider"] == "health_connect")
        assert hc_item["status"] == "connected"
        assert "sync" in hc_item["available_actions"]
        assert "pause" in hc_item["available_actions"]
        assert "disconnect" in hc_item["available_actions"]

        apple_item = next(i for i in data["integrations"] if i["provider"] == "apple_health")
        assert apple_item["status"] == "available"
        assert apple_item["available_actions"] == ["connect"]
    finally:
        db.close()


def test_integration_lifecycle_action() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="integration-action")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        # 1. Connect apple_health
        connect_resp = client.post(
            "/api/v2/you/integrations/apple_health/action",
            json={"action": "connect"},
            headers=headers,
        )
        assert connect_resp.status_code == 200
        assert connect_resp.json()["data"]["status"] == "connected"

        # 2. Pause apple_health
        pause_resp = client.post(
            "/api/v2/you/integrations/apple_health/action",
            json={"action": "pause"},
            headers=headers,
        )
        assert pause_resp.status_code == 200
        assert pause_resp.json()["data"]["status"] == "paused"

        # 3. Resume apple_health
        resume_resp = client.post(
            "/api/v2/you/integrations/apple_health/action",
            json={"action": "resume"},
            headers=headers,
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["data"]["status"] == "connected"
    finally:
        db.close()


def test_sync_connected_health_observation_endpoint() -> None:
    db = SessionLocal()
    try:
        user = _create_user(db, label="sync-user")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)
        now = datetime.now(UTC)

        payload = {
            "profile_id": profile.id,
            "source_system": "dexcom",
            "source_record_id": "cgm_val_9999",
            "source_device_id": "dexcom_g7_sensor",
            "data_type": "blood_glucose",
            "effective_start": (now - timedelta(minutes=2)).isoformat(),
            "effective_end": now.isoformat(),
            "observed_value": {"mg_dl": 105.5},
            "unit": "mg/dL",
            "source_version": "rev-1.0",
            "provenance": {"algorithm": "glucose_trend_v1"},
        }

        # 1. First sync -> creates observation
        sync_resp1 = client.post(
            "/api/v2/you/integrations/sync",
            json=payload,
            headers=headers,
        )
        assert sync_resp1.status_code == 200
        sync_data1 = sync_resp1.json()["data"]

        assert sync_data1["status"] == "synced"
        assert sync_data1["is_duplicate"] is False
        assert sync_data1["action_taken"] == "created"
        assert sync_data1["observation_id"] is not None
        assert sync_data1["source_system"] == "dexcom"
        assert sync_data1["data_type"] == "blood_glucose"

        # 2. Retry exact same payload -> returns deduplicated
        sync_resp2 = client.post(
            "/api/v2/you/integrations/sync",
            json=payload,
            headers=headers,
        )
        assert sync_resp2.status_code == 200
        sync_data2 = sync_resp2.json()["data"]

        assert sync_data2["status"] == "deduplicated"
        assert sync_data2["is_duplicate"] is True
        assert sync_data2["action_taken"] == "deduplicated_noop"
        assert sync_data2["observation_id"] == sync_data1["observation_id"]

        # Check DB row count: exactly 1 observation exists
        obs_count = db.execute(
            select(func.count(WearableObservation.id)).where(
                WearableObservation.provider_record_id == "cgm_val_9999"
            )
        ).scalar()
        assert obs_count == 1
    finally:
        db.close()


def test_get_you_overview_success() -> None:
    """GET /api/v2/you/overview returns aggregated demographics, emergency, and sharing info."""
    db = SessionLocal()
    try:
        user = _create_user(db, label="you-overview")
        profile = _create_profile(db, user, full_name="Lê Thị Overview")
        headers = _auth_headers(user, profile)

        resp = client.get("/api/v2/you/overview", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] is not None
        data = body["data"]

        assert data["profile"]["display_name"] == "Lê Thị Overview"
        assert data["profile"]["blood_type"] == "O+"
        assert data["demographics"]["full_name"] == "Lê Thị Overview"
        assert data["emergency_card"]["blood_type"] == "O+"
        assert "family_sharing" in data
        assert "privacy_ai" in data
        assert "integrations" in data
        assert "professional_mode" in data
    finally:
        db.close()


def test_update_you_profile_patch() -> None:
    """PATCH /api/v2/you/profile updates demographics and emergency fields."""
    db = SessionLocal()
    try:
        user = _create_user(db, label="you-patch")
        profile = _create_profile(db, user, full_name="Trần Văn Cũ")
        headers = _auth_headers(user, profile)

        resp = client.patch(
            "/api/v2/you/profile",
            json={
                "full_name": "Trần Văn Mới",
                "blood_type": "AB+",
                "phone": "0987654321",
                "emergency_contact": {
                    "name": "Người Thân Mới",
                    "phone": "0911223344",
                    "relationship": "Parent",
                },
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["full_name"] == "Trần Văn Mới"
        assert data["blood_type"] == "AB+"
        assert data["phone"] == "0987654321"
        assert data["emergency_contact"]["name"] == "Người Thân Mới"
    finally:
        db.close()


def test_emergency_card_and_settings() -> None:
    """GET/PUT emergency card, GET AI transparency, notifications, and security settings."""
    db = SessionLocal()
    try:
        user = _create_user(db, label="you-settings-all")
        profile = _create_profile(db, user, full_name="Hoàng Kim Card")
        headers = _auth_headers(user, profile)

        # 1. Emergency card
        card_resp = client.get("/api/v2/you/emergency-card", headers=headers)
        assert card_resp.status_code == 200
        card_data = card_resp.json()["data"]
        assert card_data["blood_type"] == "O+"

        put_card = client.put(
            "/api/v2/you/emergency-card",
            json={"blood_type": "B-"},
            headers=headers,
        )
        assert put_card.status_code == 200
        assert put_card.json()["data"]["blood_type"] == "B-"

        # 2. AI transparency
        ai_resp = client.get("/api/v2/you/privacy/ai-transparency", headers=headers)
        assert ai_resp.status_code == 200
        assert ai_resp.json()["data"]["cot_zero_disclosure"]["operates_without_cot"] is True

        # 3. Notifications
        notif_resp = client.get("/api/v2/you/notifications", headers=headers)
        assert notif_resp.status_code == 200
        assert notif_resp.json()["data"]["channels"]["push"] is True

        # 4. Security settings
        sec_resp = client.get("/api/v2/you/settings/security", headers=headers)
        assert sec_resp.status_code == 200
        assert len(sec_resp.json()["data"]["active_sessions"]) >= 1
    finally:
        db.close()
