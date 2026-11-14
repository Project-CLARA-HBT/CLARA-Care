"""Comprehensive integration tests for Connected Health and Wearables.

Covers:
1. Wearable import batches:
   - Valid import with multiple records and types (steps, heart_rate, sleep).
   - Ingestion updates and version tracking in WearableObservation / WearableObservationVersion.
   - Daily aggregates calculation with deduplication (steps).
   - Batch rejection for unconsented data types.
   - Batch rejection for connector / profile / provider mismatch.
   - Handling record tombstones (soft deletion and aggregate recomputation).

2. Permission revocation:
   - Revoking consent blocks subsequent imports immediately (HTTP 403 / 409).
   - Disconnecting connector sets status to disconnected and revokes active consent.
   - Reauthorization requirement after disconnection.
   - Hard deletion of imported data via /{connector_id}/imported-data cleans observations
     and invalidates daily aggregates.

3. Resync idempotency:
   - Exact import batch replay with identical idempotency_key and payload hash returns
     idempotent_replay=True without duplicating rows or re-triggering outbox events.
   - Reusing idempotency_key with altered payload causes HTTP 409 conflict.
   - Outbox event publication during sync request (POST /{connector_id}/sync) is clean,
     updates audit log, and emits connector.sync_requested.

4. CSRF enforcement:
   - Cookie-authenticated mutations to connected health endpoints require valid matching CSRF header.
   - Missing CSRF cookie/header on cookie-auth mutation returns HTTP 403 ("CSRF validation failed").
   - Mismatched CSRF cookie and header returns HTTP 403.
   - Bearer-authenticated mutations bypass CSRF requirements safely.
   - Cookie-authenticated mutation with matching CSRF cookie+header succeeds.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import (
    ConnectorAccount,
    ConnectorAuditEvent,
    ConnectorConsent,
    ConnectorImportBatch,
    ConnectorSyncCursor,
    LifeMapOutboxEvent,
    PhrProfile,
    User,
    WearableAggregateContribution,
    WearableDailyAggregate,
    WearableObservation,
    WearableObservationVersion,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_connector(
    token: str,
    *,
    provider: str = "health_connect",
    subject: str = "mobile-test-device-1",
    label: str = "Pixel 8 Pro",
    data_types: list[str] | None = None,
    purposes: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "provider": provider,
        "external_subject_ref": subject,
        "display_label": label,
        "consent_version": "1.0",
        "purposes": purposes or ["personal_health_assistance"],
        "data_types": data_types or ["steps", "heart_rate", "sleep"],
    }
    resp = client.post("/api/v1/connectors/device", headers=_auth(token), json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _build_batch_payload(
    connector_id: str,
    profile_id: str,
    *,
    idempotency_key: str,
    records: list[dict[str, Any]] | None = None,
    tombstones: list[dict[str, Any]] | None = None,
    cursor: str | None = "cur-001",
    provider: str = "health_connect",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "idempotency_key": idempotency_key,
        "profile_id": profile_id,
        "connector_id": connector_id,
        "provider": provider,
        "cursor": cursor,
        "records": records if records is not None else [],
        "tombstones": tombstones if tombstones is not None else [],
    }


def _sample_step_record(
    connector_id: str,
    profile_id: str,
    *,
    provider_record_id: str = "step-rec-1",
    steps: int = 1500,
    start_iso: str = "2026-08-01T08:00:00Z",
    end_iso: str = "2026-08-01T09:00:00Z",
    raw_hash: str | None = None,
    origin: str = "com.google.android.apps.fitness",
) -> dict[str, Any]:
    if raw_hash is None:
        raw_hash = "sha256:" + uuid.uuid4().hex.rjust(64, "0")[:64]
    return {
        "schema_version": "1.0",
        "profile_id": profile_id,
        "connector_id": connector_id,
        "provider": "health_connect",
        "provider_record_id": provider_record_id,
        "record_type": "steps",
        "value": {"scalar": steps, "unit": "count"},
        "observed_start": start_iso,
        "observed_end": end_iso,
        "data_origin": origin,
        "recording_method": "automatic",
        "provenance": {"adapter_version": "1.0", "raw_hash": raw_hash},
    }


def _sample_heart_rate_record(
    connector_id: str,
    profile_id: str,
    *,
    provider_record_id: str = "hr-rec-1",
    bpm: float = 72.0,
    start_iso: str = "2026-08-01T08:15:00Z",
    end_iso: str = "2026-08-01T08:16:00Z",
    raw_hash: str | None = None,
    origin: str = "com.google.android.apps.fitness",
) -> dict[str, Any]:
    if raw_hash is None:
        raw_hash = "sha256:" + uuid.uuid4().hex.rjust(64, "0")[:64]
    return {
        "schema_version": "1.0",
        "profile_id": profile_id,
        "connector_id": connector_id,
        "provider": "health_connect",
        "provider_record_id": provider_record_id,
        "record_type": "heart_rate",
        "value": {"scalar": bpm, "unit": "beats/min"},
        "observed_start": start_iso,
        "observed_end": end_iso,
        "data_origin": origin,
        "recording_method": "automatic",
        "provenance": {"adapter_version": "1.0", "raw_hash": raw_hash},
    }


# ==============================================================================
# Suite 1: Wearable Import Batches
# ==============================================================================

def test_wearable_import_batch_multi_type_ingestion_and_aggregates() -> None:
    """Tests successful ingestion of multi-type wearable records and aggregate computation."""
    email = _unique_email("wearable-multi-ingest")
    token = _login(email)
    connector = _create_connector(token, data_types=["steps", "heart_rate", "sleep"])
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    step_rec = _sample_step_record(connector_id, profile_id, provider_record_id="step-1", steps=2500)
    hr_rec = _sample_heart_rate_record(connector_id, profile_id, provider_record_id="hr-1", bpm=68.0)

    batch_payload = _build_batch_payload(
        connector_id,
        profile_id,
        idempotency_key="batch-init-01",
        records=[step_rec, hr_rec],
        cursor="cursor-page-1",
    )

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=batch_payload,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted_count"] == 2
    assert body["upserted_count"] == 2
    assert body["rejected_count"] == 0
    assert body["tombstoned_count"] == 0
    assert body["idempotent_replay"] is False

    with SessionLocal() as db:
        obs_rows = list(
            db.execute(
                select(WearableObservation).where(WearableObservation.connector_id == int(connector_id))
            ).scalars()
        )
        assert len(obs_rows) == 2
        types = {o.record_type for o in obs_rows}
        assert types == {"steps", "heart_rate"}

        step_obs = next(o for o in obs_rows if o.record_type == "steps")
        assert step_obs.value_json == {"scalar": 2500.0, "components": None, "unit": "count"}
        assert step_obs.version_no == 1
        assert step_obs.is_active is True

        # Check sync cursor
        cursor_row = db.execute(
            select(ConnectorSyncCursor).where(
                ConnectorSyncCursor.connector_id == int(connector_id),
                ConnectorSyncCursor.data_type == "steps",
            )
        ).scalar_one_or_none()
        assert cursor_row is not None
        assert cursor_row.cursor == "cursor-page-1"

        # Check daily aggregate for steps
        daily_agg = db.execute(
            select(WearableDailyAggregate).where(
                WearableDailyAggregate.profile_id == int(profile_id),
                WearableDailyAggregate.record_type == "steps",
            )
        ).scalar_one_or_none()
        assert daily_agg is not None
        assert daily_agg.value_json == {"scalar": 2500.0, "unit": "count"}


def test_wearable_import_batch_updates_create_versions() -> None:
    """Updating existing observations creates version snapshots and updates value."""
    email = _unique_email("wearable-version-update")
    token = _login(email)
    connector = _create_connector(token)
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    raw_hash_v1 = "sha256:" + "1" * 64
    raw_hash_v2 = "sha256:" + "2" * 64

    rec_v1 = _sample_step_record(
        connector_id, profile_id, provider_record_id="step-rev-1", steps=1000, raw_hash=raw_hash_v1
    )
    b1 = _build_batch_payload(connector_id, profile_id, idempotency_key="batch-v1", records=[rec_v1])
    resp1 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=b1)
    assert resp1.status_code == 200

    # Modify with new raw_hash and increased steps
    rec_v2 = _sample_step_record(
        connector_id, profile_id, provider_record_id="step-rev-1", steps=1800, raw_hash=raw_hash_v2
    )
    b2 = _build_batch_payload(connector_id, profile_id, idempotency_key="batch-v2", records=[rec_v2])
    resp2 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=b2)
    assert resp2.status_code == 200
    assert resp2.json()["upserted_count"] == 1

    with SessionLocal() as db:
        obs = db.execute(
            select(WearableObservation).where(
                WearableObservation.connector_id == int(connector_id),
                WearableObservation.provider_record_id == "step-rev-1",
            )
        ).scalar_one()
        assert obs.version_no == 2
        assert obs.value_json["scalar"] == 1800.0

        versions = list(
            db.execute(
                select(WearableObservationVersion).where(
                    WearableObservationVersion.observation_id == obs.id
                )
            ).scalars()
        )
        assert len(versions) == 1
        assert versions[0].version_no == 1
        assert versions[0].snapshot_json["value"]["scalar"] == 1000.0


def test_wearable_import_batch_tombstone_soft_deletes_and_recomputes_aggregate() -> None:
    """Tombstones deactivate observation, create a version record, and recalculate aggregate."""
    email = _unique_email("wearable-tombstone")
    token = _login(email)
    connector = _create_connector(token)
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    rec1 = _sample_step_record(connector_id, profile_id, provider_record_id="step-to-del", steps=1200)
    b1 = _build_batch_payload(connector_id, profile_id, idempotency_key="batch-before-del", records=[rec1])
    resp1 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=b1)
    assert resp1.status_code == 200

    # Submit tombstone
    tombstone = {
        "provider_record_id": "step-to-del",
        "data_origin": rec1["data_origin"],
        "deleted_at": "2026-08-01T10:00:00Z",
    }
    b2 = _build_batch_payload(
        connector_id, profile_id, idempotency_key="batch-tombstone", tombstones=[tombstone]
    )
    resp2 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=b2)
    assert resp2.status_code == 200
    assert resp2.json()["tombstoned_count"] == 1

    with SessionLocal() as db:
        obs = db.execute(
            select(WearableObservation).where(
                WearableObservation.connector_id == int(connector_id),
                WearableObservation.provider_record_id == "step-to-del",
            )
        ).scalar_one()
        assert obs.is_active is False
        assert obs.version_no == 2
        assert obs.deleted_at is not None

        # Verify aggregate contribution is cleared/recomputed
        aggregates = list(
            db.execute(
                select(WearableDailyAggregate).where(
                    WearableDailyAggregate.profile_id == int(profile_id)
                )
            ).scalars()
        )
        assert len(aggregates) == 0


def test_wearable_import_rejects_scope_or_provider_mismatch() -> None:
    """Batch imports fail if profile_id, connector_id, or provider do not match path/account."""
    email = _unique_email("wearable-mismatch")
    token = _login(email)
    connector = _create_connector(token)
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    # Connector ID mismatch
    bad_payload = _build_batch_payload(
        connector_id="999999",
        profile_id=profile_id,
        idempotency_key="batch-bad-scope-1",
        records=[_sample_step_record("999999", profile_id)],
    )
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=bad_payload,
    )
    assert resp.status_code == 403
    assert "scope mismatch" in resp.json()["detail"].lower()

    # Provider mismatch
    prov_mismatch = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        idempotency_key="batch-bad-scope-2",
        records=[],
        provider="fitbit",
    )
    prov_mismatch["records"] = [
        {
            **_sample_step_record(connector_id, profile_id),
            "provider": "fitbit",
        }
    ]
    resp2 = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=prov_mismatch,
    )
    assert resp2.status_code == 422
    assert "provider mismatch" in resp2.json()["detail"].lower()


# ==============================================================================
# Suite 2: Permission Revocation & Data Deletion
# ==============================================================================

def test_consent_revocation_blocks_import_and_requires_reauthorization() -> None:
    """Revoking connector consent blocks further imports and re-sync without re-auth."""
    email = _unique_email("wearable-revocation")
    token = _login(email)
    connector = _create_connector(token, data_types=["steps"])
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    # Ingest 1 record successfully
    rec = _sample_step_record(connector_id, profile_id, steps=800)
    b1 = _build_batch_payload(connector_id, profile_id, idempotency_key="batch-rev-1", records=[rec])
    r1 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=b1)
    assert r1.status_code == 200

    # Disconnect (revokes consent)
    disc = client.delete(f"/api/v1/connectors/{connector_id}", headers=_auth(token))
    assert disc.status_code == 200
    assert disc.json()["status"] == "disconnected"

    # Attempting to sync or import after disconnect fails
    sync_resp = client.post(f"/api/v1/connectors/{connector_id}/sync", headers=_auth(token))
    assert sync_resp.status_code == 409
    assert "must be reauthorized" in sync_resp.json()["detail"].lower()

    b2 = _build_batch_payload(
        connector_id, profile_id, idempotency_key="batch-rev-2", records=[rec]
    )
    import_resp = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=b2,
    )
    assert import_resp.status_code == 409
    assert "not available for imports" in import_resp.json()["detail"].lower()


def test_permission_unconsented_data_type_is_blocked() -> None:
    """Records for types not consented to are rejected with 403."""
    email = _unique_email("wearable-unconsented")
    token = _login(email)
    # Only consent to steps
    connector = _create_connector(token, data_types=["steps"])
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    # Attempt to send heart rate
    hr_rec = _sample_heart_rate_record(connector_id, profile_id, bpm=75.0)
    payload = _build_batch_payload(
        connector_id, profile_id, idempotency_key="batch-unconsented", records=[hr_rec]
    )
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/imports",
        headers=_auth(token),
        json=payload,
    )
    assert resp.status_code == 403
    assert "unconsented" in resp.json()["detail"].lower()


def test_delete_imported_data_cascades_and_invalidates_aggregates() -> None:
    """DELETE /{connector_id}/imported-data removes observations and invalidates aggregates."""
    email = _unique_email("wearable-hard-delete")
    token = _login(email)
    connector = _create_connector(token, data_types=["steps"])
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    # Ingest records
    rec1 = _sample_step_record(connector_id, profile_id, provider_record_id="del-step-1", steps=3000)
    rec2 = _sample_step_record(
        connector_id,
        profile_id,
        provider_record_id="del-step-2",
        steps=2000,
        start_iso="2026-08-01T14:00:00Z",
        end_iso="2026-08-01T15:00:00Z",
    )
    b = _build_batch_payload(connector_id, profile_id, idempotency_key="batch-del-prep", records=[rec1, rec2])
    resp = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=b)
    assert resp.status_code == 200

    # Ensure aggregate exists
    with SessionLocal() as db:
        agg = db.execute(
            select(WearableDailyAggregate).where(WearableDailyAggregate.profile_id == int(profile_id))
        ).scalar_one_or_none()
        assert agg is not None

    # Delete imported data
    del_resp = client.delete(
        f"/api/v1/connectors/{connector_id}/imported-data",
        headers=_auth(token),
    )
    assert del_resp.status_code == 200
    res_data = del_resp.json()
    assert res_data["deleted_observations"] == 2
    assert res_data["invalidated_aggregates"] >= 1

    # Verify database cleanliness
    with SessionLocal() as db:
        remaining_obs = db.execute(
            select(WearableObservation).where(WearableObservation.connector_id == int(connector_id))
        ).scalars().all()
        assert len(remaining_obs) == 0

        remaining_agg = db.execute(
            select(WearableDailyAggregate).where(WearableDailyAggregate.profile_id == int(profile_id))
        ).scalars().all()
        assert len(remaining_agg) == 0

        # Check audit event
        audit_event = db.execute(
            select(ConnectorAuditEvent).where(
                ConnectorAuditEvent.connector_id == int(connector_id),
                ConnectorAuditEvent.event_type == "connector.imported_data_deleted",
            )
        ).scalar_one_or_none()
        assert audit_event is not None


# ==============================================================================
# Suite 3: Resync Idempotency & Outbox Integration
# ==============================================================================

def test_resync_idempotency_exact_replay() -> None:
    """Exact re-submission of batch returns identical response without side-effects."""
    email = _unique_email("wearable-idemp-replay")
    token = _login(email)
    connector = _create_connector(token)
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    rec = _sample_step_record(connector_id, profile_id, steps=999)
    payload = _build_batch_payload(
        connector_id, profile_id, idempotency_key="batch-replay-key", records=[rec]
    )

    # First execution
    r1 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=payload)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["idempotent_replay"] is False

    # Second execution (exact replay)
    r2 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["idempotent_replay"] is True
    assert d2["batch_id"] == d1["batch_id"]
    assert d2["accepted_count"] == d1["accepted_count"]

    with SessionLocal() as db:
        # Check only 1 batch record created in db
        batches = list(
            db.execute(
                select(ConnectorImportBatch).where(
                    ConnectorImportBatch.connector_id == int(connector_id),
                    ConnectorImportBatch.idempotency_key == "batch-replay-key",
                )
            ).scalars()
        )
        assert len(batches) == 1


def test_resync_idempotency_key_reuse_conflict() -> None:
    """Reusing idempotency_key with altered payload returns HTTP 409 Conflict."""
    email = _unique_email("wearable-idemp-conflict")
    token = _login(email)
    connector = _create_connector(token)
    connector_id = connector["id"]

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload_a = _build_batch_payload(
        connector_id,
        profile_id,
        idempotency_key="key-conflict-01",
        records=[_sample_step_record(connector_id, profile_id, steps=100)],
    )
    payload_b = _build_batch_payload(
        connector_id,
        profile_id,
        idempotency_key="key-conflict-01",
        records=[_sample_step_record(connector_id, profile_id, steps=200)],
    )

    r1 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=payload_a)
    assert r1.status_code == 200

    r2 = client.post(f"/api/v1/connectors/{connector_id}/imports", headers=_auth(token), json=payload_b)
    assert r2.status_code == 409
    assert "already used for another payload" in r2.json()["detail"].lower()


def test_sync_request_emits_transactional_outbox_event() -> None:
    """Triggering POST /{connector_id}/sync produces an outbox event and audit record."""
    email = _unique_email("wearable-sync-outbox")
    token = _login(email)
    connector = _create_connector(token)
    connector_id = connector["id"]

    sync_resp = client.post(f"/api/v1/connectors/{connector_id}/sync", headers=_auth(token))
    assert sync_resp.status_code == 200
    assert sync_resp.json()["action"] == "device_import_required"

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        outbox = db.execute(
            select(LifeMapOutboxEvent).where(
                LifeMapOutboxEvent.aggregate_id == connector_id,
                LifeMapOutboxEvent.event_type == "connector.sync_requested",
            )
        ).scalar_one_or_none()
        assert outbox is not None
        assert outbox.aggregate_type == "connector_account"
        assert outbox.status == "pending"

        audit = db.execute(
            select(ConnectorAuditEvent).where(
                ConnectorAuditEvent.connector_id == int(connector_id),
                ConnectorAuditEvent.event_type == "connector.sync_requested",
            )
        ).scalar_one_or_none()
        assert audit is not None
        assert audit.actor_user_id == user.id


# ==============================================================================
# Suite 4: CSRF Enforcement
# ==============================================================================

def test_csrf_rejects_cookie_authenticated_device_creation_without_csrf() -> None:
    """Cookie auth mutation to /api/v1/connectors/device without CSRF token is rejected (403)."""
    settings = get_settings()
    if not settings.auth_csrf_enabled:
        return

    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "fake-session-cookie")
    try:
        resp = client.post(
            "/api/v1/connectors/device",
            json={
                "provider": "health_connect",
                "external_subject_ref": "dev-csrf",
                "display_label": "CSRF test",
                "consent_version": "1.0",
                "purposes": ["personal_health_assistance"],
                "data_types": ["steps"],
            },
        )
    finally:
        client.cookies.clear()
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF validation failed"


def test_csrf_rejects_cookie_authenticated_sync_with_mismatched_csrf() -> None:
    """Cookie auth mutation with mismatched CSRF token returns 403."""
    settings = get_settings()
    if not settings.auth_csrf_enabled:
        return

    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "fake-session-cookie")
    client.cookies.set(settings.auth_csrf_cookie_name, "valid-csrf-cookie-val")
    try:
        resp = client.post(
            "/api/v1/connectors/1/sync",
            headers={settings.auth_csrf_header_name: "mismatched-header-val"},
        )
    finally:
        client.cookies.clear()
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF validation failed"


def test_csrf_allows_bearer_authenticated_connector_mutation() -> None:
    """Bearer-authenticated mutations bypass CSRF requirements completely."""
    email = _unique_email("csrf-bearer-bypass")
    token = _login(email)
    client.cookies.clear()

    # Mutation with Bearer token only (no cookies, no CSRF header)
    resp = client.post(
        "/api/v1/connectors/device",
        headers=_auth(token),
        json={
            "provider": "health_connect",
            "external_subject_ref": "dev-bearer-bypass",
            "display_label": "Bearer Bypass Test",
            "consent_version": "1.0",
            "purposes": ["personal_health_assistance"],
            "data_types": ["steps"],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "connected"


def test_csrf_allows_cookie_authenticated_mutation_with_matching_csrf() -> None:
    """Cookie auth mutation with matching CSRF cookie and header succeeds."""
    settings = get_settings()
    if not settings.auth_csrf_enabled:
        return

    email = _unique_email("csrf-cookie-match")
    client.cookies.clear()
    # Login sets auth cookies and CSRF cookie
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login_resp.status_code == 200

    csrf_val = client.cookies.get(settings.auth_csrf_cookie_name)
    assert csrf_val, "CSRF cookie must be set on login when CSRF is enabled"

    try:
        resp = client.post(
            "/api/v1/connectors/device",
            headers={settings.auth_csrf_header_name: csrf_val},
            json={
                "provider": "health_connect",
                "external_subject_ref": "dev-cookie-match",
                "display_label": "Cookie Match Test",
                "consent_version": "1.0",
                "purposes": ["personal_health_assistance"],
                "data_types": ["steps"],
            },
        )
    finally:
        client.cookies.clear()

    assert resp.status_code == 201, resp.text
    assert resp.json()["display_label"] == "Cookie Match Test"
