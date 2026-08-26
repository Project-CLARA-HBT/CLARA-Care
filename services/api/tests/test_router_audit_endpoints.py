import pytest
from fastapi.testclient import TestClient

from clara_api.core.security import create_access_token
from clara_api.db.models import PhrProfile, User
from clara_api.db.session import SessionLocal
from clara_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_callback_missing_code(client: TestClient):
    resp = client.post("/api/v1/auth/callback", json={"code": ""})
    assert resp.status_code == 422 or resp.status_code == 400


def test_auth_callback_valid_user(client: TestClient):
    with SessionLocal() as db_session:
        user = User(
            email="test_callback@clara.local",
            hashed_password="hashed_dummy_pw",
            role="doctor",
            full_name="Doctor Callback",
            status="active",
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    resp = client.post("/api/v1/auth/callback", json={"code": "test_callback@clara.local"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "doctor"
    assert "access_token" in data
    assert data["access_token"] is not None


def test_clinical_workbench_patients_alias(client: TestClient):
    with SessionLocal() as db_session:
        user = User(
            email="workbench_doc@clara.local",
            hashed_password="hashed_dummy_pw",
            role="doctor",
            full_name="Doctor Workbench",
            status="active",
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    token = create_access_token(subject="workbench_doc@clara.local", role="doctor")
    headers = {"Authorization": f"Bearer {token}"}

    # Test both /clinical-workbench/patients and /clinical/workbench/patients
    r1 = client.get("/api/v1/clinical-workbench/patients", headers=headers)
    assert r1.status_code == 200

    r2 = client.get("/api/v1/clinical/workbench/patients", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == r1.json()


def test_v2_security_settings_and_sessions(client: TestClient):
    with SessionLocal() as db_session:
        user = User(
            email="v2_user_sec@clara.local",
            hashed_password="hashed_dummy_pw",
            role="normal",
            full_name="User Sec",
            status="active",
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    token = create_access_token(subject="v2_user_sec@clara.local", role="normal")
    headers = {"Authorization": f"Bearer {token}"}

    # GET /api/v2/you/settings/security
    r_get = client.get("/api/v2/you/settings/security", headers=headers)
    assert r_get.status_code == 200
    data_get = r_get.json()
    assert data_get["data"]["mfa_enabled"] is False

    # PATCH /api/v2/you/settings/security
    r_patch = client.patch(
        "/api/v2/you/settings/security",
        headers=headers,
        json={"mfa_enabled": True, "inactivity_timeout_minutes": 15},
    )
    assert r_patch.status_code == 200
    data_patch = r_patch.json()
    assert data_patch["data"]["mfa_enabled"] is True
    assert data_patch["data"]["inactivity_timeout_minutes"] == 15

    # DELETE /api/v2/you/settings/sessions/{id}
    r_del = client.delete("/api/v2/you/settings/sessions/sess-123", headers=headers)
    assert r_del.status_code == 200
    assert r_del.json()["data"]["success"] is True

    # POST /api/v2/you/settings/sessions/revoke-others
    r_rev = client.post("/api/v2/you/settings/sessions/revoke-others", headers=headers, json={})
    assert r_rev.status_code == 200
    assert r_rev.json()["data"]["success"] is True


def test_v2_health_medications_alias(client: TestClient):
    with SessionLocal() as db_session:
        user = User(
            email="v2_med_user@clara.local",
            hashed_password="hashed_dummy_pw",
            role="normal",
            full_name="User Med",
            status="active",
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        profile = PhrProfile(
            public_id="PRF-TEST-MED-1",
            user_id=user.id,
            allergies_json=[],
            medications_json=[],
            conditions_json=[],
        )
        db_session.add(profile)
        db_session.commit()

    token = create_access_token(subject="v2_med_user@clara.local", role="normal")
    headers = {"Authorization": f"Bearer {token}", "X-CLARA-Profile-Context": "PRF-TEST-MED-1"}

    # Check both /api/v2/medications/hub and /api/v2/health/medications/hub
    r1 = client.get("/api/v2/medications/hub", headers=headers)
    assert r1.status_code == 200

    r2 = client.get("/api/v2/health/medications/hub", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["data"] == r1.json()["data"]
