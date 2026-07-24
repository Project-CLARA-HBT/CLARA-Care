from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import (
    ConnectorAccount,
    ConnectorAuditEvent,
    ConnectorConsent,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create(token: str, *, subject: str = "android-device-1"):
    return client.post(
        "/api/v1/connectors/device",
        headers=_auth(token),
        json={
            "provider": "health_connect",
            "external_subject_ref": subject,
            "display_label": "Điện thoại của tôi",
            "consent_version": "1.0",
            "purposes": ["personal_health_assistance"],
            "data_types": ["steps", "heart_rate", "sleep"],
        },
    )


def test_capabilities_are_authenticated_and_explicit() -> None:
    assert client.get("/api/v1/connectors/capabilities").status_code == 401
    token = _login("connector-capabilities@example.com")

    response = client.get("/api/v1/connectors/capabilities", headers=_auth(token))

    assert response.status_code == 200
    by_provider = {item["provider"]: item for item in response.json()}
    assert set(by_provider) == {"health_connect", "huawei_health", "wear_os", "fitbit"}
    assert by_provider["health_connect"]["client_detection_required"] is True
    assert "steps" in by_provider["health_connect"]["supported_data_types"]


def test_connector_lifecycle_consent_and_audit() -> None:
    token = _login("connector-lifecycle@example.com")

    created = _create(token)
    assert created.status_code == 201, created.text
    connector = created.json()
    connector_id = connector["id"]
    assert connector["status"] == "connected"
    assert connector["purposes"] == ["personal_health_assistance"]
    assert connector["data_types"] == ["steps", "heart_rate", "sleep"]

    duplicate = _create(token)
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/connectors", headers=_auth(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [connector_id]

    sync = client.post(
        f"/api/v1/connectors/{connector_id}/sync",
        headers=_auth(token),
    )
    assert sync.status_code == 200
    assert sync.json()["action"] == "device_import_required"
    assert sync.json()["connector"]["last_synced_at"] is None

    paused = client.post(
        f"/api/v1/connectors/{connector_id}/pause",
        headers=_auth(token),
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert (
        client.post(
            f"/api/v1/connectors/{connector_id}/sync",
            headers=_auth(token),
        ).status_code
        == 409
    )

    resumed = client.post(
        f"/api/v1/connectors/{connector_id}/resume",
        headers=_auth(token),
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "connected"

    disconnected = client.delete(
        f"/api/v1/connectors/{connector_id}",
        headers=_auth(token),
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["status"] == "disconnected"
    assert disconnected.json()["purposes"] == []

    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.email == "connector-lifecycle@example.com")
        ).scalar_one()
        account = db.execute(
            select(ConnectorAccount).where(ConnectorAccount.user_id == user.id)
        ).scalar_one()
        consent = db.execute(
            select(ConnectorConsent).where(ConnectorConsent.connector_id == account.id)
        ).scalar_one()
        events = list(
            db.execute(
                select(ConnectorAuditEvent).where(
                    ConnectorAuditEvent.connector_id == account.id
                )
            ).scalars()
        )
    assert consent.revoked_at is not None
    assert [event.event_type for event in events] == [
        "connector.authorized",
        "connector.sync_requested",
        "connector.paused",
        "connector.connected",
        "connector.disconnected",
    ]
    assert account.token_ciphertext is None


def test_connector_ids_do_not_cross_user_boundaries() -> None:
    owner_token = _login("connector-owner@example.com")
    stranger_token = _login("connector-stranger@example.com")
    connector_id = _create(owner_token).json()["id"]

    for method, suffix in (
        ("post", "pause"),
        ("post", "resume"),
        ("post", "sync"),
        ("delete", "imported-data"),
    ):
        response = getattr(client, method)(
            f"/api/v1/connectors/{connector_id}/{suffix}",
            headers=_auth(stranger_token),
        )
        assert response.status_code == 404

    disconnect = client.delete(
        f"/api/v1/connectors/{connector_id}",
        headers=_auth(stranger_token),
    )
    assert disconnect.status_code == 404
    assert client.get("/api/v1/connectors", headers=_auth(stranger_token)).json() == []


def test_device_connector_rejects_duplicate_scope_values() -> None:
    token = _login("connector-invalid@example.com")
    response = client.post(
        "/api/v1/connectors/device",
        headers=_auth(token),
        json={
            "provider": "health_connect",
            "external_subject_ref": "device",
            "purposes": [
                "personal_health_assistance",
                "personal_health_assistance",
            ],
            "data_types": ["steps"],
        },
    )
    assert response.status_code == 422
