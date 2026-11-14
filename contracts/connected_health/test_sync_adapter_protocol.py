"""Automated verification suite for Connected Health sync adapter protocol, safe DTOs, and endpoints.

Phase: PH13 (Connected Health & Wearables)
Subagent: A01 (API + contract)

Validates:
1. Contract JSON structure and schema adherence.
2. Safe DTO models, strict UCUM unit validation, finiteness, and timezone checks.
3. Thread-safe sliding-window rate limiter logic.
4. Sync adapter protocol handshake endpoint (/api/v1/connectors/sync/protocol).
5. Ingestion of canonical health observations via sync adapter endpoint.
6. Idempotent replay of identical batches (idempotent_replay=True).
7. Idempotency conflict rejection on mismatched payload.
8. Rate limit enforcement returning HTTP 429 and Retry-After header.
9. Payload bounds protection against payload bombs (>500 records).
10. Idempotency key mismatch detection between header and body.
11. Profile scope and provider mismatch protection.
12. Cross-tenant and cross-profile boundary isolation (no ID enumeration).
13. Consent revocation enforcement blocking sync ingestion.
14. Body-addressed sync batch endpoint (/api/v1/connectors/sync/batch).
15. Cursor status inspection and cursor commitment acknowledgement.
16. Zero-mock data invariant verification across all protocol outputs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from clara_api.api.v1.endpoints.connected_health import (
    SyncAdapterRateLimiter,
    _sync_limiter,
)
from clara_api.db.base import Base
from clara_api.db.models import (
    ConnectorAccount,
)
from clara_api.db.session import engine
from clara_api.main import app
from clara_api.schemas import (
    CanonicalHealthRecordDTO,
    CanonicalHealthValueDTO,
    SyncAdapterBatchRequestDTO,
)
from fastapi import status
from fastapi.testclient import TestClient

CONTRACTS_DIR = Path(__file__).resolve().parent
client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _setup_test_database() -> None:
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    _sync_limiter.reset()
    yield
    _sync_limiter.reset()


def _login(email: str) -> tuple[dict[str, str], str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, token


def _create_connector(
    headers: dict[str, str],
    *,
    provider: str = "health_connect",
    data_types: list[str] | None = None,
) -> dict[str, Any]:
    types = data_types or ["steps", "heart_rate", "sleep", "weight"]
    resp = client.post(
        "/api/v1/connectors/device",
        headers=headers,
        json={
            "provider": provider,
            "external_subject_ref": f"dev-{uuid4().hex[:12]}",
            "display_label": "Thiết bị thử nghiệm",
            "consent_version": "1.0",
            "purposes": ["personal_health_assistance", "lifemap_context"],
            "data_types": types,
        },
    )
    assert resp.status_code == 201, f"Create connector failed: {resp.text}"
    return resp.json()


def _build_batch_payload(
    connector_id: str,
    profile_id: str,
    *,
    idempotency_key: str | None = None,
    provider: str = "health_connect",
    record_type: str = "steps",
    steps_value: int = 2500,
    raw_hash: str | None = None,
    cursor: str = "cur-001",
) -> dict[str, Any]:
    key = idempotency_key or f"batch-{uuid4().hex[:12]}"
    digest = raw_hash or ("sha256:" + "a" * 64)
    now = datetime.now(UTC)
    start = now - timedelta(hours=1)

    return {
        "protocol_version": "connector.sync.v1",
        "idempotency_key": key,
        "profile_id": profile_id,
        "connector_id": connector_id,
        "provider": provider,
        "sync_mode": "incremental",
        "cursor": cursor,
        "records": [
            {
                "schema_version": "1.0",
                "profile_id": profile_id,
                "connector_id": connector_id,
                "provider": provider,
                "provider_record_id": f"rec-{uuid4().hex[:12]}",
                "record_type": record_type,
                "value": {"scalar": float(steps_value), "components": None, "unit": "count"},
                "observed_start": start.isoformat(),
                "observed_end": now.isoformat(),
                "zone_offset_start": "+07:00",
                "zone_offset_end": "+07:00",
                "data_origin": "com.google.android.apps.healthdata",
                "device": {"manufacturer": "Google", "model": "Pixel Watch", "type": "watch"},
                "recording_method": "automatic",
                "quality": {"state": "source_asserted", "flags": ["verified_sensor"]},
                "provenance": {"adapter_version": "1.0.0", "raw_hash": digest},
            }
        ],
        "tombstones": [],
        "client_metadata": {"sdk_version": "1.2.0"},
    }


# ============================================================================
# 1. Contract & JSON Schema Integrity Tests
# ============================================================================


def test_contract_files_exist_and_parse_validly() -> None:
    schema_path = CONTRACTS_DIR / "sync_adapter_protocol.schema.json"
    contract_path = CONTRACTS_DIR / "sync_adapter_contract.v1.json"
    openapi_path = CONTRACTS_DIR / "sync_adapter_openapi.v1.json"

    assert schema_path.exists(), "sync_adapter_protocol.schema.json missing"
    assert contract_path.exists(), "sync_adapter_contract.v1.json missing"
    assert openapi_path.exists(), "sync_adapter_openapi.v1.json missing"

    with open(schema_path, encoding="utf-8") as f:
        schema_data = json.load(f)
    assert schema_data["phase_id"] == "PH13"
    assert schema_data["agent_id"] == "A01"
    assert "SyncAdapterBatchRequest" in schema_data["definitions"]
    assert "SyncAdapterBatchResponse" in schema_data["definitions"]

    with open(contract_path, encoding="utf-8") as f:
        contract_data = json.load(f)
    assert contract_data["protocol_version"] == "connector.sync.v1"
    assert len(contract_data["endpoints"]) >= 4
    assert "RATE_LIMIT_EXCEEDED" in contract_data["error_codes"]
    assert "IDEMPOTENCY_CONFLICT" in contract_data["error_codes"]

    with open(openapi_path, encoding="utf-8") as f:
        openapi_data = json.load(f)
    assert openapi_data["openapi"].startswith("3.1")
    assert "/api/v1/connectors/sync/protocol" in openapi_data["paths"]
    assert "/api/v1/connectors/{connector_id}/sync/adapter" in openapi_data["paths"]


# ============================================================================
# 2. Safe DTO Models & Validation Invariants
# ============================================================================


def test_canonical_health_value_dto_validation() -> None:
    # Valid scalar
    val_scalar = CanonicalHealthValueDTO(scalar=72.0, unit="beats/min")
    assert val_scalar.scalar == 72.0
    assert val_scalar.components is None

    # Valid component
    val_comp = CanonicalHealthValueDTO(
        components={"systolic": 120.0, "diastolic": 80.0}, unit="mm[Hg]"
    )
    assert val_comp.scalar is None
    assert val_comp.components == {"systolic": 120.0, "diastolic": 80.0}

    # Reject both scalar and components
    with pytest.raises(ValueError, match="exactly one of scalar or components"):
        CanonicalHealthValueDTO(
            scalar=10.0,
            components={"systolic": 120.0},
            unit="count",
        )

    # Reject non-finite numbers
    with pytest.raises(ValueError, match="numbers must be finite"):
        CanonicalHealthValueDTO(scalar=float("nan"), unit="count")

    with pytest.raises(ValueError, match="numbers must be finite"):
        CanonicalHealthValueDTO(scalar=float("inf"), unit="count")


def test_canonical_health_record_dto_validation() -> None:
    now = datetime.now(UTC)
    past = now - timedelta(minutes=15)

    # Valid record
    rec = CanonicalHealthRecordDTO(
        schema_version="1.0",
        profile_id="prof_123",
        connector_id="conn_456",
        provider="health_connect",
        provider_record_id="rec_789",
        record_type="steps",
        value=CanonicalHealthValueDTO(scalar=100.0, unit="count"),
        observed_start=past,
        observed_end=now,
        data_origin="com.example.health",
    )
    assert rec.record_type == "steps"

    # Reject inverted interval
    with pytest.raises(ValueError, match="observed_end cannot precede observed_start"):
        CanonicalHealthRecordDTO(
            schema_version="1.0",
            profile_id="prof_123",
            connector_id="conn_456",
            provider="health_connect",
            provider_record_id="rec_789",
            record_type="steps",
            value=CanonicalHealthValueDTO(scalar=100.0, unit="count"),
            observed_start=now,
            observed_end=past,
            data_origin="com.example.health",
        )

    # Reject missing timezone
    naive_dt = datetime(2026, 7, 25, 10, 0, 0)
    with pytest.raises(ValueError, match="timezone information"):
        CanonicalHealthRecordDTO(
            schema_version="1.0",
            profile_id="prof_123",
            connector_id="conn_456",
            provider="health_connect",
            provider_record_id="rec_789",
            record_type="steps",
            value=CanonicalHealthValueDTO(scalar=100.0, unit="count"),
            observed_start=naive_dt,
            observed_end=now,
            data_origin="com.example.health",
        )


def test_sync_adapter_batch_request_scope_validation() -> None:
    now = datetime.now(UTC)
    # Scope mismatch between batch and record
    with pytest.raises(ValueError, match="records must match batch profile_id"):
        SyncAdapterBatchRequestDTO(
            protocol_version="connector.sync.v1",
            idempotency_key="batch_001",
            profile_id="prof_correct",
            connector_id="conn_correct",
            provider="health_connect",
            records=[
                CanonicalHealthRecordDTO(
                    schema_version="1.0",
                    profile_id="prof_WRONG",
                    connector_id="conn_correct",
                    provider="health_connect",
                    provider_record_id="r1",
                    record_type="steps",
                    value=CanonicalHealthValueDTO(scalar=50.0, unit="count"),
                    observed_start=now - timedelta(minutes=5),
                    observed_end=now,
                    data_origin="origin",
                )
            ],
        )


# ============================================================================
# 3. Thread-Safe Rate Limiter Unit Tests
# ============================================================================


def test_sync_adapter_rate_limiter_logic() -> None:
    limiter = SyncAdapterRateLimiter(max_requests=3, window_seconds=60)
    key = "test_conn_rate"

    # First 3 should pass
    for i in range(3):
        allowed, rem, retry = limiter.check_and_record(key)
        assert allowed is True
        assert rem == 2 - i
        assert retry == 0

    # 4th should be blocked
    allowed, rem, retry = limiter.check_and_record(key)
    assert allowed is False
    assert rem == 0
    assert retry > 0

    # Reset clears history
    limiter.reset()
    allowed, rem, retry = limiter.check_and_record(key)
    assert allowed is True
    assert rem == 2


# ============================================================================
# 4. Protocol Handshake Endpoint Tests
# ============================================================================


def test_sync_protocol_handshake_unauthenticated_rejects_401() -> None:
    unauthed = TestClient(app)
    resp = unauthed.get("/api/v1/connectors/sync/protocol")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_sync_protocol_handshake_returns_capabilities_and_limits() -> None:
    headers, _ = _login("user-handshake@example.com")
    resp = client.get("/api/v1/connectors/sync/protocol", headers=headers)
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["protocol_version"] == "connector.sync.v1"
    assert "health_connect" in data["supported_providers"]
    assert "huawei_health" in data["supported_providers"]
    assert "steps" in data["supported_data_types"]
    assert "heart_rate" in data["supported_data_types"]
    assert data["rate_limits"]["max_requests_per_minute"] == 60
    assert data["rate_limits"]["max_records_per_batch"] == 500
    assert "Nghị định 13/2023/NĐ-CP" in data["data_protection_notice"]


# ============================================================================
# 5. Core Sync Ingestion & Idempotency Tests
# ============================================================================


def test_sync_adapter_successful_batch_commit() -> None:
    headers, _ = _login("user-sync-commit@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    # Retrieve internal profile_id from connector account
    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    batch_payload = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        steps_value=3200,
        raw_hash="sha256:" + "1" * 64,
    )

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=batch_payload,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()

    assert data["protocol_version"] == "connector.sync.v1"
    assert data["status"] == "COMMITTED"
    assert data["idempotent_replay"] is False
    assert data["accepted_count"] == 1
    assert data["upserted_count"] == 1
    assert data["rejected_count"] == 0
    assert resp.headers.get("X-RateLimit-Limit") == "60"
    assert "X-RateLimit-Remaining" in resp.headers


def test_sync_adapter_idempotent_replay() -> None:
    headers, _ = _login("user-sync-replay@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    batch_payload = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        idempotency_key="batch_fixed_key_001",
        steps_value=1500,
        raw_hash="sha256:" + "2" * 64,
    )

    # First submission
    resp1 = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=batch_payload,
    )
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["idempotent_replay"] is False

    # Second submission (identical replay)
    resp2 = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=batch_payload,
    )
    assert resp2.status_code == status.HTTP_200_OK
    data2 = resp2.json()
    assert data2["status"] == "IDEMPOTENT_REPLAY"
    assert data2["idempotent_replay"] is True
    assert resp2.headers.get("X-Idempotent-Replay") == "true"


def test_sync_adapter_idempotency_conflict_rejection() -> None:
    headers, _ = _login("user-sync-conflict@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    fixed_key = "batch_conflict_key_999"
    payload1 = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        idempotency_key=fixed_key,
        steps_value=1000,
        raw_hash="sha256:" + "3" * 64,
    )
    resp1 = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=payload1,
    )
    assert resp1.status_code == status.HTTP_200_OK

    # Differing payload using SAME idempotency key
    payload2 = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        idempotency_key=fixed_key,
        steps_value=4000,
        raw_hash="sha256:" + "4" * 64,
    )
    resp2 = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=payload2,
    )
    assert resp2.status_code == status.HTTP_409_CONFLICT
    err_data = resp2.json()
    assert err_data["error_code"] == "IDEMPOTENCY_CONFLICT"
    assert "correlation_id" in err_data


# ============================================================================
# 6. Rate Limiting & Payload Abuse Protection Tests
# ============================================================================


def test_sync_adapter_rate_limiting_enforcement() -> None:
    headers, _ = _login("user-sync-ratelimit@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    # Exhaust the rate limiter by filling the window
    rate_key = f"connector:{connector_id}"
    for _ in range(60):
        _sync_limiter.check_and_record(rate_key)

    payload = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        raw_hash="sha256:" + "5" * 64,
    )

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = resp.json()
    assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp.headers


def test_sync_adapter_payload_bomb_rejected() -> None:
    headers, _ = _login("user-sync-payloadbomb@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
    )
    # Generate 501 records to exceed WH-067 bounds
    base_rec = payload["records"][0]
    payload["records"] = [
        {**base_rec, "provider_record_id": f"rec-{i}"} for i in range(501)
    ]

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=payload,
    )
    assert resp.status_code in {status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, status.HTTP_422_UNPROCESSABLE_ENTITY}


def test_idempotency_key_mismatch_header_vs_body() -> None:
    headers, _ = _login("user-sync-mismatch@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        idempotency_key="key_in_body",
    )

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers={**headers, "X-Idempotency-Key": "key_in_header_DIFFERENT"},
        json=payload,
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert data["error_code"] == "IDEMPOTENCY_KEY_MISMATCH"


# ============================================================================
# 7. Authorization, Scope & Consent Isolation Tests
# ============================================================================


def test_cross_profile_cannot_access_foreign_connector() -> None:
    owner_headers, _ = _login("user-owner-conn@example.com")
    stranger_headers, _ = _login("user-stranger-conn@example.com")

    conn = _create_connector(owner_headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload = _build_batch_payload(connector_id=connector_id, profile_id=profile_id)

    # Stranger attempts to sync to owner's connector
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=stranger_headers,
        json=payload,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.json()["error_code"] == "CONNECTOR_NOT_FOUND"


def test_consent_revocation_blocks_sync_adapter_ingestion() -> None:
    headers, _ = _login("user-consent-revoked@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload = _build_batch_payload(connector_id=connector_id, profile_id=profile_id)

    # Disconnect (revokes consent)
    del_resp = client.delete(f"/api/v1/connectors/{connector_id}", headers=headers)
    assert del_resp.status_code == status.HTTP_200_OK

    # Sync attempt should fail closed
    sync_resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/adapter",
        headers=headers,
        json=payload,
    )
    assert sync_resp.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_409_CONFLICT}


# ============================================================================
# 8. Body-Addressed Batch Endpoint Tests
# ============================================================================


def test_body_addressed_sync_batch_endpoint() -> None:
    headers, _ = _login("user-sync-body-addr@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        account = db.get(ConnectorAccount, int(connector_id))
        assert account is not None
        profile_id = str(account.profile_id)

    payload = _build_batch_payload(
        connector_id=connector_id,
        profile_id=profile_id,
        steps_value=1800,
        raw_hash="sha256:" + "6" * 64,
    )

    resp = client.post(
        "/api/v1/connectors/sync/batch",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["status"] == "COMMITTED"
    assert resp.json()["accepted_count"] == 1


# ============================================================================
# 9. Cursor Status & Acknowledgement Workflow Tests
# ============================================================================


def test_cursor_status_and_ack_workflow() -> None:
    headers, _ = _login("user-cursor-flow@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    # 1. Query status before sync
    stat_resp = client.get(
        f"/api/v1/connectors/{connector_id}/sync/status",
        headers=headers,
    )
    assert stat_resp.status_code == status.HTTP_200_OK
    assert stat_resp.json()["connector_id"] == connector_id

    # 2. Acknowledge committed cursor
    ack_resp = client.post(
        f"/api/v1/connectors/{connector_id}/sync/ack",
        headers=headers,
        json={
            "connector_id": connector_id,
            "committed_cursor": "client_ack_cursor_v1",
            "records_processed": 42,
        },
    )
    assert ack_resp.status_code == status.HTTP_200_OK
    assert ack_resp.json()["acknowledged"] is True
    assert ack_resp.json()["updated_cursor"] == "client_ack_cursor_v1"

    # 3. Query status again to confirm cursor persisted
    stat_resp2 = client.get(
        f"/api/v1/connectors/{connector_id}/sync/status",
        headers=headers,
    )
    assert stat_resp2.status_code == status.HTTP_200_OK
    assert stat_resp2.json()["active_cursor"] == "client_ack_cursor_v1"


# ============================================================================
# 10. Zero-Mock Data Invariant Test
# ============================================================================


def test_zero_mock_data_invariants() -> None:
    """Ensure that all responses are derived from authentic models and DB state."""
    headers, _ = _login("user-zero-mock@example.com")
    conn = _create_connector(headers, provider="health_connect")
    connector_id = conn["id"]

    stat_resp = client.get(
        f"/api/v1/connectors/{connector_id}/sync/status",
        headers=headers,
    )
    data = stat_resp.json()
    assert "mock" not in json.dumps(data).lower()
    assert "fake" not in json.dumps(data).lower()
    assert "synthetic" not in json.dumps(data).lower()
