from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import (
    ConnectorAccount,
    ConnectorAuditEvent,
    ConnectorConsent,
    ConnectorSyncCursor,
    GlhsAssertion,
    User,
    WearableAggregateContribution,
    WearableDailyAggregate,
    WearableObservation,
    WearableObservationVersion,
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


def _record_payload(connector_id: str, profile_id: str, *, raw_hash: str, steps: int = 1200):
    return {
        "schema_version": "1.0",
        "idempotency_key": "batch_import_1",
        "profile_id": profile_id,
        "connector_id": connector_id,
        "provider": "health_connect",
        "cursor": "cursor-1",
        "records": [
            {
                "schema_version": "1.0",
                "profile_id": profile_id,
                "connector_id": connector_id,
                "provider": "health_connect",
                "provider_record_id": "steps-record-1",
                "record_type": "steps",
                "value": {"scalar": steps, "unit": "count"},
                "observed_start": "2026-07-25T01:00:00Z",
                "observed_end": "2026-07-25T02:00:00Z",
                "data_origin": "com.example.health",
                "recording_method": "automatic",
                "provenance": {"adapter_version": "1.0", "raw_hash": raw_hash},
            }
        ],
    }


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


def test_import_is_atomic_idempotent_and_versions_changed_records() -> None:
    token = _login("connector-import@example.com")
    connector_id = _create(token).json()["id"]
    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    first_payload = _record_payload(
        connector_id,
        profile_id,
        raw_hash="sha256:" + "a" * 64,
    )
    first = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=first_payload,
    )
    assert first.status_code == 200, first.text
    assert first.json() == {
        "batch_id": "1",
        "idempotent_replay": False,
        "accepted_count": 1,
        "rejected_count": 0,
        "upserted_count": 1,
        "tombstoned_count": 0,
    }

    replay = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=first_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    changed = _record_payload(
        connector_id,
        profile_id,
        raw_hash="sha256:" + "b" * 64,
        steps=1400,
    )
    changed["idempotency_key"] = "batch_import_2"
    second = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=changed,
    )
    assert second.status_code == 200
    assert second.json()["upserted_count"] == 1

    with SessionLocal() as db:
        observation = db.execute(select(WearableObservation)).scalar_one()
        version = db.execute(select(WearableObservationVersion)).scalar_one()
        cursor = db.execute(select(ConnectorSyncCursor)).scalar_one()
        aggregate = db.execute(select(WearableDailyAggregate)).scalar_one()
        contribution = db.execute(select(WearableAggregateContribution)).scalar_one()
        assertions = list(
            db.execute(
                select(GlhsAssertion)
                .where(GlhsAssertion.profile_id == observation.profile_id)
                .order_by(GlhsAssertion.id)
            ).scalars()
        )
    assert observation.value_json == {"scalar": 1400.0, "components": None, "unit": "count"}
    assert observation.version_no == 2
    assert version.version_no == 1
    assert cursor.cursor == "cursor-1"
    assert aggregate.value_json == {"scalar": 1400.0, "unit": "count"}
    assert aggregate.primary_origin == "com.example.health"
    assert contribution.observation_id == observation.id
    assert [item.lifecycle_status for item in assertions] == ["superseded", "active"]
    assert assertions[-1].epistemic_state == "documented"
    assert assertions[-1].value_json["record_type"] == "steps"
    assert assertions[-1].value_json["value"]["scalar"] == 1400.0

    changed["idempotency_key"] = "batch_import_1"
    conflict = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=changed,
    )
    assert conflict.status_code == 409


def test_steps_projection_never_sums_overlapping_records() -> None:
    token = _login("connector-overlap@example.com")
    connector_id = _create(token).json()["id"]
    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)
    payload = _record_payload(
        connector_id,
        profile_id,
        raw_hash="sha256:" + "d" * 64,
        steps=500,
    )
    duplicate_interval = dict(payload["records"][0])
    duplicate_interval["provider_record_id"] = "steps-record-2"
    duplicate_interval["value"] = {"scalar": 800, "unit": "count"}
    duplicate_interval["provenance"] = {
        "adapter_version": "1.0",
        "raw_hash": "sha256:" + "e" * 64,
    }
    payload["records"].append(duplicate_interval)

    response = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        aggregate = db.execute(select(WearableDailyAggregate)).scalar_one()
        contributions = list(db.execute(select(WearableAggregateContribution)).scalars())
    assert aggregate.value_json == {"scalar": 800.0, "unit": "count"}
    assert len(contributions) == 1


def test_import_blocks_revoked_or_unconsented_data_types() -> None:
    token = _login("connector-import-consent@example.com")
    connector_id = _create(token).json()["id"]
    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload = _record_payload(
        connector_id,
        profile_id,
        raw_hash="sha256:" + "c" * 64,
    )
    payload["records"][0]["record_type"] = "blood_glucose"
    payload["records"][0]["value"] = {"scalar": 5.4, "unit": "mmol/L"}
    assert (
        client.post(
            f"/api/v1/connectors/{connector_id}/imports",
            headers=_auth(token),
            json=payload,
        ).status_code
        == 403
    )

    client.delete(f"/api/v1/connectors/{connector_id}", headers=_auth(token))
    payload["records"][0]["record_type"] = "steps"
    payload["records"][0]["value"] = {"scalar": 100, "unit": "count"}
    assert (
        client.post(
            f"/api/v1/connectors/{connector_id}/imports",
            headers=_auth(token),
            json=payload,
        ).status_code
        == 409
    )
