"""Tests for CLARA API v2 conventions, error envelopes, and router integration."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Header
from fastapi.testclient import TestClient
from pydantic import BaseModel

from clara_api.api.v2.conventions import (
    ApiV2ErrorEnvelope,
    ApiV2HTTPException,
    ApiV2ResponseEnvelope,
    BaseVersionPrecondition,
    CursorPaginationParams,
    IdempotencyKeyHelper,
    MessageMetadata,
    PaginatedResponse,
)
from clara_api.main import app


# ---------------------------------------------------------------------------
# Unit tests: MessageMetadata
# ---------------------------------------------------------------------------
def test_message_metadata_fields():
    meta = MessageMetadata(
        key="messages.item_saved",
        params={"item_id": "item-123"},
        severity="success",
        action_target="/items/item-123",
    )
    assert meta.key == "messages.item_saved"
    assert meta.params == {"item_id": "item-123"}
    assert meta.severity == "success"
    assert meta.action_target == "/items/item-123"

    # Default values
    default_meta = MessageMetadata(key="info.ready")
    assert default_meta.params == {}
    assert default_meta.severity == "info"
    assert default_meta.action_target is None


# ---------------------------------------------------------------------------
# Unit tests: ApiV2ResponseEnvelope
# ---------------------------------------------------------------------------
def test_response_envelope_wrapping():
    envelope = ApiV2ResponseEnvelope.wrap(
        data={"user": "Alice", "role": "doctor"},
        meta={"server_time": "2026-08-19T00:00:00Z"},
        message=MessageMetadata(key="notices.welcome"),
        warnings=[MessageMetadata(key="warnings.profile_unverified", severity="warning")],
    )
    assert envelope.data == {"user": "Alice", "role": "doctor"}
    assert envelope.meta == {"server_time": "2026-08-19T00:00:00Z"}
    assert envelope.message is not None
    assert envelope.message.key == "notices.welcome"
    assert len(envelope.warnings) == 1
    assert envelope.warnings[0].key == "warnings.profile_unverified"


def test_response_envelope_minimal():
    envelope = ApiV2ResponseEnvelope.wrap(data="hello")
    assert envelope.data == "hello"
    assert envelope.meta is None
    assert envelope.message is None
    assert envelope.warnings == []


# ---------------------------------------------------------------------------
# Unit tests: ApiV2ErrorEnvelope & ApiV2HTTPException
# ---------------------------------------------------------------------------
def test_error_envelope_structure_and_conversion():
    error = ApiV2ErrorEnvelope(
        code="state_conflict",
        message_key="errors.state_conflict",
        message="Resource was updated concurrently",
        params={"resource": "profile"},
        details={"diff": ["name"]},
        safe_to_reapply=False,
        current_version=42,
        changed_fields=["name"],
    )
    assert error.code == "state_conflict"
    assert error.message_key == "errors.state_conflict"
    assert error.safe_to_reapply is False
    assert error.current_version == 42
    assert error.changed_fields == ["name"]

    data = error.to_dict()
    assert data["code"] == "state_conflict"
    assert data["safe_to_reapply"] is False
    assert data["current_version"] == 42
    assert data["changed_fields"] == ["name"]

    response = error.as_response(status_code=409)
    assert response.status_code == 409

    exc = error.as_exception(status_code=409)
    assert isinstance(exc, ApiV2HTTPException)
    assert exc.status_code == 409
    assert exc.error.code == "state_conflict"


def test_apiv2_http_exception_construction():
    exc = ApiV2HTTPException(
        status_code=412,
        code="precondition_failed",
        message="Version mismatch",
        current_version="v3",
        changed_fields=["allergies"],
        safe_to_reapply=False,
    )
    assert exc.status_code == 412
    assert exc.error.code == "precondition_failed"
    assert exc.error.current_version == "v3"
    assert exc.error.changed_fields == ["allergies"]
    assert exc.error.safe_to_reapply is False


# ---------------------------------------------------------------------------
# Unit tests: CursorPaginationParams & PaginatedResponse
# ---------------------------------------------------------------------------
def test_cursor_pagination_encode_decode_roundtrip():
    payload = {"id": 105, "ts": 1724000000, "sort": "desc"}
    token = CursorPaginationParams.encode_cursor(payload)
    assert isinstance(token, str)
    assert len(token) > 0

    decoded = CursorPaginationParams.decode_cursor(token)
    assert decoded == payload

    # Primitive values
    token_scalar = CursorPaginationParams.encode_cursor(42)
    decoded_scalar = CursorPaginationParams.decode_cursor(token_scalar)
    assert decoded_scalar == {"v": 42}

    # Empty / None handling
    assert CursorPaginationParams.decode_cursor(None) is None
    assert CursorPaginationParams.decode_cursor("   ") is None


def test_cursor_pagination_invalid_cursor_raises_422():
    with pytest.raises(ApiV2HTTPException) as exc_info:
        CursorPaginationParams.decode_cursor("not-valid-base64-!@#$%^")
    assert exc_info.value.status_code == 422
    assert exc_info.value.error.code == "invalid_cursor"


def test_paginated_response_helpers():
    items = ["item1", "item2", "item3"]
    response = PaginatedResponse.create(
        items=items,
        next_cursor="cur_next",
        prev_cursor="cur_prev",
        total_count=100,
    )
    assert response.items == items
    assert response.next_cursor == "cur_next"
    assert response.prev_cursor == "cur_prev"
    assert response.has_more is True
    assert response.total_count == 100

    # Auto has_more when next_cursor is present
    auto_response = PaginatedResponse.create(items=["a"], next_cursor="tok")
    assert auto_response.has_more is True

    # Empty response
    empty_response = PaginatedResponse.create(items=[])
    assert empty_response.has_more is False
    assert empty_response.next_cursor is None


# ---------------------------------------------------------------------------
# Unit tests: BaseVersionPrecondition
# ---------------------------------------------------------------------------
def test_etag_formatting_and_parsing():
    assert BaseVersionPrecondition.format_etag("42") == '"42"'
    assert BaseVersionPrecondition.format_etag('"42"') == '"42"'
    assert BaseVersionPrecondition.format_etag(42, weak=True) == 'W/"42"'

    assert BaseVersionPrecondition.parse_etag('"42"') == "42"
    assert BaseVersionPrecondition.parse_etag('W/"42"') == "42"
    assert BaseVersionPrecondition.parse_etag("  42  ") == "42"
    assert BaseVersionPrecondition.parse_etag(None) is None


def test_validate_precondition_success():
    # Matching version
    BaseVersionPrecondition.validate_precondition('"5"', 5)
    BaseVersionPrecondition.validate_precondition('W/"5"', "5")
    # Wildcard
    BaseVersionPrecondition.validate_precondition("*", 5)
    # None allowed
    BaseVersionPrecondition.validate_precondition(None, 5, allow_none=True)


def test_validate_precondition_failures():
    # Version mismatch raises 412
    with pytest.raises(ApiV2HTTPException) as exc_info:
        BaseVersionPrecondition.validate_precondition(
            '"4"', 5, changed_fields=["medications"]
        )
    assert exc_info.value.status_code == 412
    assert exc_info.value.error.code == "state_conflict"
    assert exc_info.value.error.current_version == "5"
    assert exc_info.value.error.changed_fields == ["medications"]
    assert exc_info.value.error.safe_to_reapply is False

    # Required but missing raises 428
    with pytest.raises(ApiV2HTTPException) as exc_info:
        BaseVersionPrecondition.validate_precondition(None, 5, allow_none=False)
    assert exc_info.value.status_code == 428
    assert exc_info.value.error.code == "precondition_required"


def test_validate_base_version():
    # Matching version
    BaseVersionPrecondition.validate_base_version(10, 10)
    BaseVersionPrecondition.validate_base_version("10", 10)
    BaseVersionPrecondition.validate_base_version(None, 10, allow_none=True)

    # Mismatch raises 409
    with pytest.raises(ApiV2HTTPException) as exc_info:
        BaseVersionPrecondition.validate_base_version(
            9, 10, changed_fields=["allergies"]
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error.code == "state_conflict"
    assert exc_info.value.error.current_version == "10"
    assert exc_info.value.error.changed_fields == ["allergies"]
    assert exc_info.value.error.safe_to_reapply is False

    # Required but missing raises 428
    with pytest.raises(ApiV2HTTPException) as exc_info:
        BaseVersionPrecondition.validate_base_version(None, 10, allow_none=False)
    assert exc_info.value.status_code == 428
    assert exc_info.value.error.code == "base_version_required"


# ---------------------------------------------------------------------------
# Unit tests: IdempotencyKeyHelper
# ---------------------------------------------------------------------------
def test_idempotency_key_validation():
    assert IdempotencyKeyHelper.validate_key("req-12345") == "req-12345"
    assert IdempotencyKeyHelper.validate_key("  req-clean  ") == "req-clean"
    assert IdempotencyKeyHelper.validate_key(None, required=False) is None

    # Missing required key -> 422
    with pytest.raises(ApiV2HTTPException) as exc_info:
        IdempotencyKeyHelper.validate_key("", required=True)
    assert exc_info.value.status_code == 422
    assert exc_info.value.error.code == "missing_idempotency_key"

    # Too long key -> 422
    with pytest.raises(ApiV2HTTPException) as exc_info:
        IdempotencyKeyHelper.validate_key("x" * 129)
    assert exc_info.value.status_code == 422
    assert exc_info.value.error.code == "invalid_idempotency_key"


def test_idempotency_hashing_and_digest():
    key_hash = IdempotencyKeyHelper.compute_key_hash("test-key-1")
    assert isinstance(key_hash, str)
    assert len(key_hash) == 64

    # Digest ordering invariance
    d1 = IdempotencyKeyHelper.compute_request_digest(
        {"a": 1, "b": 2}, method="POST", path="/api/v2/test"
    )
    d2 = IdempotencyKeyHelper.compute_request_digest(
        {"b": 2, "a": 1}, method="POST", path="/api/v2/test"
    )
    assert d1 == d2

    # Different payload yields different digest
    d3 = IdempotencyKeyHelper.compute_request_digest(
        {"a": 1, "b": 3}, method="POST", path="/api/v2/test"
    )
    assert d1 != d3


def test_idempotency_digest_conflict_check():
    d1 = IdempotencyKeyHelper.compute_request_digest({"action": "save"})
    d2 = IdempotencyKeyHelper.compute_request_digest({"action": "delete"})

    # Matching digest passes
    IdempotencyKeyHelper.check_digest_conflict(d1, d1)

    # Mismatched digest raises 409
    with pytest.raises(ApiV2HTTPException) as exc_info:
        IdempotencyKeyHelper.check_digest_conflict(d1, d2)
    assert exc_info.value.status_code == 409
    assert exc_info.value.error.code == "idempotency_conflict"
    assert exc_info.value.error.safe_to_reapply is False


# ---------------------------------------------------------------------------
# Integration tests: App mounting and FastAPI Exception Handler
# ---------------------------------------------------------------------------
def test_v2_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/v2/health")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == {"status": "ok", "version": "v2", "service": "clara-api"}
    assert data["meta"] == {"api_version": "2.0"}


class _TestConflictPayload(BaseModel):
    base_version: int


def test_v2_exception_handler_returns_error_envelope():
    # Use an isolated FastAPI app to test the exception handler without polluting global app routes
    from fastapi import FastAPI

    from clara_api.main import api_v2_exception_handler

    test_app = FastAPI()
    test_app.add_exception_handler(ApiV2HTTPException, api_v2_exception_handler)

    test_router = APIRouter(prefix="/api/v2/test-conventions")

    @test_router.post("/conflict")
    def conflict_endpoint(
        payload: _TestConflictPayload,
        if_match: str | None = Header(default=None, alias="If-Match"),
    ):
        BaseVersionPrecondition.validate_precondition(
            if_match, current_version=5, changed_fields=["title"]
        )
        BaseVersionPrecondition.validate_base_version(
            payload.base_version, current_version=5, changed_fields=["title"]
        )
        return {"ok": True}

    test_app.include_router(test_router)
    client = TestClient(test_app)

    # 1. Test If-Match mismatch -> 412 with ApiV2ErrorEnvelope
    res_412 = client.post(
        "/api/v2/test-conventions/conflict",
        headers={"If-Match": '"3"'},
        json={"base_version": 5},
    )
    assert res_412.status_code == 412
    err_412 = res_412.json()
    assert err_412["code"] == "state_conflict"
    assert err_412["current_version"] == "5"
    assert err_412["changed_fields"] == ["title"]
    assert err_412["safe_to_reapply"] is False

    # 2. Test base_version mismatch -> 409 with ApiV2ErrorEnvelope
    res_409 = client.post(
        "/api/v2/test-conventions/conflict",
        headers={"If-Match": '"5"'},
        json={"base_version": 4},
    )
    assert res_409.status_code == 409
    err_409 = res_409.json()
    assert err_409["code"] == "state_conflict"
    assert err_409["current_version"] == "5"
    assert err_409["safe_to_reapply"] is False
