"""Automated verification suite for LifeMap timeline event query contracts, DTOs, and API endpoints.

Phase: PH12 (LifeMap longitudinal intelligence)
Subagent: A01 (API + contract)

Validates:
1. Contract JSON structure and JSON schema adherence.
2. Pydantic safe DTO models and strict field validation.
3. PHI payload sanitization and data protection invariants.
4. Keyset cursor encoding, decoding, and error handling.
5. Feature flag gating (allow and deny paths).
6. RBAC access control and multi-tenant profile isolation.
7. Bitemporal filtering and deterministic temporal ordering.
8. Single timeline event safe query by public ID.
9. Contract introspection endpoint metadata.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from clara_api.api.v1.endpoints.lifemap import (
    _decode_timeline_cursor,
    _encode_timeline_cursor,
    _sanitize_event_payload,
    is_timeline_query_v2_enabled,
)
from clara_api.db.base import Base
from clara_api.db.session import engine
from clara_api.main import app
from clara_api.schemas import (
    SafeTimelineEventDTO,
    TimelineQueryPagination,
    TimelineQueryResponse,
    TimelineQueryWindow,
    TimelineSourceReferenceDTO,
)
from fastapi import status
from fastapi.testclient import TestClient

CONTRACTS_DIR = Path(__file__).resolve().parent
client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _setup_test_database() -> None:
    Base.metadata.create_all(bind=engine)
    yield



def _load_json(file_path: Path) -> dict[str, Any]:
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# 1. Contract & JSON Schema Adherence
# ============================================================================


def test_contract_json_files_exist_and_parse() -> None:
    schema_path = CONTRACTS_DIR / "timeline_event_contract.schema.json"
    contract_path = CONTRACTS_DIR / "timeline_query_contract.v1.json"
    openapi_path = CONTRACTS_DIR / "timeline_query_openapi.v1.json"

    assert schema_path.is_file(), "Schema contract file missing"
    assert contract_path.is_file(), "Contract file missing"
    assert openapi_path.is_file(), "OpenAPI file missing"

    schema = _load_json(schema_path)
    contract = _load_json(contract_path)
    openapi = _load_json(openapi_path)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["phase_id"] == "PH12"
    assert "SafeTimelineEvent" in schema["definitions"]
    assert "TimelinePagination" in schema["definitions"]

    assert contract["phase_id"] == "PH12"
    assert contract["feature_flag"] == "LIFEMAP_TIMELINE_QUERY_V2_ENABLED"
    assert contract["invariants"]["strictly_pseudonymized_dto"] is True
    assert contract["invariants"]["bitemporal_deterministic_ordering"] is True

    assert openapi["openapi"] == "3.1.0"
    assert "/api/v1/lifemap/timeline/events" in openapi["paths"]
    assert "/api/v1/lifemap/events/{event_id}" in openapi["paths"]
    assert "/api/v1/lifemap/timeline/contract" in openapi["paths"]


# ============================================================================
# 2. Pydantic Safe DTO Model Validation
# ============================================================================


def test_safe_timeline_event_dto_serialization() -> None:
    now = datetime.now(UTC)
    dto = SafeTimelineEventDTO(
        id="evt-safe-123",
        event_type="medication",
        truth_state="confirmed",
        occurred_at=now,
        recorded_at=now,
        title="Amlodipine 5mg",
        display_summary="Uống 1 viên sau ăn sáng",
        payload={"dose_mg": 5, "frequency": "once_daily"},
        provenance={"attribution": "Bác sĩ kê đơn"},
        source_kind="clinical",
        revision_no=1,
        source_reference=TimelineSourceReferenceDTO(
            source_id="src-001",
            source_kind="prescription",
            original_language="vi",
            checksum="abc123sha256",
        ),
        confidence=0.98,
    )
    dumped = dto.model_dump()
    assert dumped["id"] == "evt-safe-123"
    assert dumped["event_type"] == "medication"
    assert dumped["source_reference"]["checksum"] == "abc123sha256"
    assert dumped["confidence"] == 0.98

    # Extra fields ignored gracefully
    raw_with_extra = {
        "id": "evt-extra",
        "event_type": "symptom",
        "truth_state": "user_reported",
        "occurred_at": now.isoformat(),
        "title": "Đau đầu",
        "unknown_extra_field": 12345,
    }
    loaded = SafeTimelineEventDTO.model_validate(raw_with_extra)
    assert loaded.id == "evt-extra"
    assert not hasattr(loaded, "unknown_extra_field")


def test_timeline_query_response_envelope() -> None:
    now = datetime.now(UTC)
    resp = TimelineQueryResponse(
        generated_at=now,
        profile_id="prf_test123",
        items=[],
        pagination=TimelineQueryPagination(
            limit=50,
            offset=0,
            has_more=False,
            total_count=0,
        ),
        query_window=TimelineQueryWindow(),
    )
    assert resp.profile_id == "prf_test123"
    assert "bảo vệ nghiêm ngặt" in resp.data_protection_notice


# ============================================================================
# 3. PHI Payload Sanitization and Safe Title
# ============================================================================


def test_phi_sanitization_removes_direct_identifiers() -> None:
    dirty_payload = {
        "systolic": 135,
        "diastolic": 85,
        "phone": "0912345678",
        "citizen_id": "001200001234",
        "email": "patient@hospital.vn",
        "home_address": "123 Đường Lê Lợi, Q1, TP.HCM",
        "nested": {
            "doctor_name": "BS. Hoàng",
            "ssn": "999-88-7777",
            "heart_rate": 72,
        },
        "contact_list": [
            {"name": "Người thân", "phone_number": "0987654321"},
            {"relationship": "Bác sĩ gia đình"},
        ],
    }
    sanitized = _sanitize_event_payload(dirty_payload)
    assert sanitized["systolic"] == 135
    assert sanitized["phone"] == "[REDACTED_PHI]"
    assert sanitized["citizen_id"] == "[REDACTED_PHI]"
    assert sanitized["email"] == "[REDACTED_PHI]"
    assert sanitized["home_address"] == "[REDACTED_PHI]"
    assert sanitized["nested"]["ssn"] == "[REDACTED_PHI]"
    assert sanitized["nested"]["heart_rate"] == 72
    assert sanitized["contact_list"][0]["phone_number"] == "[REDACTED_PHI]"


# ============================================================================
# 4. Keyset Cursor Encoding and Decoding
# ============================================================================


def test_timeline_cursor_roundtrip() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    cursor = _encode_timeline_cursor("occurred_at", now, 42)
    decoded_dt, decoded_id = _decode_timeline_cursor(cursor, expected_sort_by="occurred_at")
    assert decoded_dt == now
    assert decoded_id == 42


def test_timeline_cursor_sort_mismatch_raises_422() -> None:
    now = datetime.now(UTC)
    cursor = _encode_timeline_cursor("recorded_at", now, 100)
    with pytest.raises(Exception) as excinfo:
        _decode_timeline_cursor(cursor, expected_sort_by="occurred_at")
    assert "cursor_sort_mismatch" in str(excinfo.value.detail)


def test_timeline_cursor_malformed_raises_422() -> None:
    with pytest.raises(Exception) as excinfo:
        _decode_timeline_cursor("invalid_not_base64!", expected_sort_by="occurred_at")
    assert "invalid_cursor" in str(excinfo.value.detail)


# ============================================================================
# 5. Feature Flag Gating (Allow and Deny Paths)
# ============================================================================


def _create_user_with_consent() -> tuple[dict[str, str], str]:
    suffix = uuid4().hex
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": f"timeline-test-{suffix}@normal.clara", "password": "secret123"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.put("/api/v1/phr/record", headers=headers, json={"full_name": f"Patient {suffix}"})
    status_resp = client.get("/api/v1/auth/consent-status", headers=headers).json()
    client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"accepted": True, "consent_version": status_resp["required_version"]},
    )
    profiles = client.get("/api/v1/profiles", headers=headers).json()
    profile_id = profiles[0]["id"]
    return headers, profile_id


def test_feature_flag_disabled_by_default_returns_404(monkeypatch) -> None:
    monkeypatch.delenv("LIFEMAP_TIMELINE_QUERY_V2_ENABLED", raising=False)
    assert not is_timeline_query_v2_enabled()

    headers, _ = _create_user_with_consent()
    resp = client.get("/api/v1/lifemap/timeline/events", headers=headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.json()["detail"]["code"] == "lifemap_timeline_query_v2_disabled"

    event_resp = client.get("/api/v1/lifemap/events/non-existent-id", headers=headers)
    assert event_resp.status_code == status.HTTP_404_NOT_FOUND
    assert event_resp.json()["detail"]["code"] == "lifemap_timeline_query_v2_disabled"

    # Contract metadata returns 200 indicating feature_flag_status = False
    meta_resp = client.get("/api/v1/lifemap/timeline/contract")
    assert meta_resp.status_code == status.HTTP_200_OK
    assert meta_resp.json()["feature_flag_status"] is False


def test_feature_flag_enabled_allows_query_execution(monkeypatch) -> None:
    monkeypatch.setenv("LIFEMAP_TIMELINE_QUERY_V2_ENABLED", "true")
    assert is_timeline_query_v2_enabled()

    headers, profile_id = _create_user_with_consent()
    resp = client.get("/api/v1/lifemap/timeline/events", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "items" in data
    assert "pagination" in data
    assert data["profile_id"] == profile_id

    # Contract endpoint reflects enabled flag
    meta = client.get("/api/v1/lifemap/timeline/contract").json()
    assert meta["feature_flag_status"] is True


# ============================================================================
# 6. RBAC & Access Control
# ============================================================================


def test_timeline_endpoints_unauthenticated_rejects_401(monkeypatch) -> None:
    monkeypatch.setenv("LIFEMAP_TIMELINE_QUERY_V2_ENABLED", "true")
    unauthed_client = TestClient(app)
    resp = unauthed_client.get("/api/v1/lifemap/timeline/events")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    resp_single = unauthed_client.get("/api/v1/lifemap/events/any-id")
    assert resp_single.status_code == status.HTTP_401_UNAUTHORIZED


def test_cross_profile_isolation(monkeypatch) -> None:
    monkeypatch.setenv("LIFEMAP_TIMELINE_QUERY_V2_ENABLED", "true")
    headers_a, profile_a = _create_user_with_consent()
    headers_b, profile_b = _create_user_with_consent()

    # User B attempts to access Profile A context without grant -> scope_forbidden (404/403)
    resp = client.get(
        "/api/v1/lifemap/timeline/events",
        headers={**headers_b, "X-CLARA-Profile-Context": profile_a},
    )
    assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
    assert resp.json()["detail"]["code"] == "scope_forbidden"


# ============================================================================
# 7. Bitemporal Filtering, Sorting, and Pagination
# ============================================================================


def test_timeline_events_bitemporal_query_and_keyset_pagination(monkeypatch) -> None:
    monkeypatch.setenv("LIFEMAP_TIMELINE_QUERY_V2_ENABLED", "true")
    headers, profile_id = _create_user_with_consent()

    # Create 3 events with distinct occurred_at timestamps
    now = datetime.now(UTC)
    t1 = now - timedelta(days=3)
    t2 = now - timedelta(days=2)
    t3 = now - timedelta(days=1)

    ev1 = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"ev1-{uuid4().hex}"},
        json={
            "event_type": "symptom",
            "occurred_at": t1.isoformat(),
            "payload": {"title": "Triệu chứng 1", "systolic": 120},
            "truth_state": "user_reported",
        },
    ).json()
    ev2 = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"ev2-{uuid4().hex}"},
        json={
            "event_type": "medication",
            "occurred_at": t2.isoformat(),
            "payload": {"title": "Thuốc 2", "drug": "Amlodipine"},
            "truth_state": "user_reported",
        },
    ).json()
    # Confirm ev2
    client.post(
        f"/api/v1/lifemap/events/{ev2['id']}/confirm",
        headers={**headers, "Idempotency-Key": f"ev2-confirm-{uuid4().hex}"},
        json={"reason": "Xác nhận uống thuốc"},
    )
    ev3 = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"ev3-{uuid4().hex}"},
        json={
            "event_type": "symptom",
            "occurred_at": t3.isoformat(),
            "payload": {"title": "Triệu chứng 3", "headache": True},
            "truth_state": "draft",
        },
    ).json()

    # Query 1: Default descending order (t3 -> t2 -> t1)
    res_desc = client.get("/api/v1/lifemap/timeline/events?order_direction=desc", headers=headers)
    assert res_desc.status_code == 200
    items_desc = res_desc.json()["items"]
    assert len(items_desc) >= 3
    ids_desc = [item["id"] for item in items_desc]
    assert ids_desc.index(ev3["id"]) < ids_desc.index(ev2["id"]) < ids_desc.index(ev1["id"])

    # Query 2: Ascending order (t1 -> t2 -> t3)
    res_asc = client.get("/api/v1/lifemap/timeline/events?order_direction=asc", headers=headers)
    assert res_asc.status_code == 200
    items_asc = res_asc.json()["items"]
    ids_asc = [item["id"] for item in items_asc]
    assert ids_asc.index(ev1["id"]) < ids_asc.index(ev2["id"]) < ids_asc.index(ev3["id"])

    # Query 3: Bitemporal filter by valid_time_from and valid_time_to
    cutoff_from = (t1 + timedelta(hours=12)).isoformat()
    cutoff_to = (t3 - timedelta(hours=12)).isoformat()
    res_bounded = client.get(
        f"/api/v1/lifemap/timeline/events?valid_time_from={cutoff_from}&valid_time_to={cutoff_to}",
        headers=headers,
    )
    assert res_bounded.status_code == 200
    bounded_ids = [it["id"] for it in res_bounded.json()["items"]]
    assert ev2["id"] in bounded_ids
    assert ev1["id"] not in bounded_ids
    assert ev3["id"] not in bounded_ids

    # Query 4: Invalid time range returns 422
    inv_res = client.get(
        f"/api/v1/lifemap/timeline/events?valid_time_from={cutoff_to}&valid_time_to={cutoff_from}",
        headers=headers,
    )
    assert inv_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Query 5: Event type filter
    med_res = client.get("/api/v1/lifemap/timeline/events?event_types=medication", headers=headers)
    assert med_res.status_code == 200
    med_ids = [it["id"] for it in med_res.json()["items"]]
    assert ev2["id"] in med_ids
    assert ev1["id"] not in med_ids

    # Query 6: Truth state filter (confirmed matches only ev2)
    state_res = client.get("/api/v1/lifemap/timeline/events?truth_states=confirmed", headers=headers)
    assert state_res.status_code == 200
    state_ids = [it["id"] for it in state_res.json()["items"]]
    assert ev2["id"] in state_ids
    assert ev1["id"] not in state_ids
    assert ev3["id"] not in state_ids

    # Query 7: Keyset cursor pagination (limit=1)
    p1 = client.get("/api/v1/lifemap/timeline/events?limit=1&order_direction=desc", headers=headers).json()
    assert len(p1["items"]) == 1
    assert p1["pagination"]["has_more"] is True
    assert p1["pagination"]["next_cursor"] is not None

    p2 = client.get(
        f"/api/v1/lifemap/timeline/events?limit=1&order_direction=desc&cursor={p1['pagination']['next_cursor']}",
        headers=headers,
    ).json()
    assert len(p2["items"]) == 1
    assert p2["items"][0]["id"] != p1["items"][0]["id"]


# ============================================================================
# 8. Single Event Query
# ============================================================================


def test_get_individual_event_by_id(monkeypatch) -> None:
    monkeypatch.setenv("LIFEMAP_TIMELINE_QUERY_V2_ENABLED", "true")
    headers, profile_id = _create_user_with_consent()

    created = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"single-ev-{uuid4().hex}"},
        json={
            "event_type": "vitals",
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": {
                "title": "Huyết áp buổi sáng",
                "systolic": 128,
                "diastolic": 80,
                "phone": "0901234567",
            },
            "truth_state": "confirmed",
        },
    ).json()

    event_id = created["id"]
    get_res = client.get(f"/api/v1/lifemap/events/{event_id}", headers=headers)
    assert get_res.status_code == status.HTTP_200_OK
    ev_dto = get_res.json()
    assert ev_dto["id"] == event_id
    assert ev_dto["event_type"] == "vitals"
    assert ev_dto["title"] == "Huyết áp buổi sáng"
    assert ev_dto["payload"]["phone"] == "[REDACTED_PHI]"
    assert ev_dto["payload"]["systolic"] == 128

    # Non-existent ID returns 404
    missing_res = client.get("/api/v1/lifemap/events/non-existent-uuid-12345", headers=headers)
    assert missing_res.status_code == status.HTTP_404_NOT_FOUND
    assert missing_res.json()["detail"]["code"] == "event_not_found"
