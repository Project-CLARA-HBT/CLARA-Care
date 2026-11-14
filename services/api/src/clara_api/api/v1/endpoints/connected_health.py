"""Connected-health connector control plane and sync adapter protocol."""

import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.connected_health.control import (
    ConnectorCapabilityResponse,
    ConnectorImportResponse,
    ConnectorOperationResponse,
    ConnectorResponse,
    DeviceConnectorCreateRequest,
    ImportedDataDeletionResponse,
)
from clara_api.connected_health.ingestion import import_batch
from clara_api.connected_health.schemas import (
    CanonicalHealthRecord,
    CanonicalHealthValue,
    ConnectorDevice,
    ConnectorImportBatch,
    ConnectorProvenance,
    ConnectorProvider,
    ConnectorQuality,
    ConnectorRecordTombstone,
    HealthRecordType,
    RecordingMethod,
)
from clara_api.connected_health.service import (
    active_consent,
    audit,
    create_device_connector,
    delete_imported_data,
    disconnect,
    owned_connector,
    request_sync,
    serialize_connector,
    transition,
)
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ConnectorAccount,
    ConnectorSyncCursor,
    User,
)
from clara_api.db.session import get_db
from clara_api.schemas import (
    SyncAdapterBatchRequestDTO,
    SyncAdapterBatchResponseDTO,
    SyncAdapterCursorAckRequestDTO,
    SyncAdapterCursorAckResponseDTO,
    SyncAdapterCursorResponseDTO,
    SyncAdapterErrorEnvelope,
    SyncAdapterProtocolHandshakeResponse,
    SyncRateLimitStatusDTO,
)

router = APIRouter()
USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))

_COMMON_TYPES = list(HealthRecordType)
_CAPABILITIES = [
    ConnectorCapabilityResponse(
        provider=ConnectorProvider.HEALTH_CONNECT,
        transport="device",
        client_detection_required=True,
        supported_data_types=_COMMON_TYPES,
        limitations=["Android availability and permissions must be detected on-device."],
    ),
    ConnectorCapabilityResponse(
        provider=ConnectorProvider.HUAWEI_HEALTH,
        transport="device",
        client_detection_required=True,
        supported_data_types=_COMMON_TYPES,
        limitations=["Huawei Health availability and permissions must be detected on-device."],
    ),
    ConnectorCapabilityResponse(
        provider=ConnectorProvider.WEAR_OS,
        transport="device",
        client_detection_required=True,
        supported_data_types=[
            HealthRecordType.STEPS,
            HealthRecordType.ACTIVITY,
            HealthRecordType.HEART_RATE,
        ],
        limitations=["Wear OS companion support is not enabled until a compatible watch is found."],
    ),
    ConnectorCapabilityResponse(
        provider=ConnectorProvider.FITBIT,
        transport="cloud",
        client_detection_required=False,
        supported_data_types=_COMMON_TYPES,
        limitations=["Requires Fitbit OAuth and vendor application approval."],
    ),
]


class SyncAdapterRateLimiter:
    """Sliding window thread-safe rate limiter for sync adapter endpoints."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._history: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, key: str, limit: int | None = None) -> tuple[bool, int, int]:
        max_req = limit or self.max_requests
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._history[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_req:
                oldest = q[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, 0, retry_after
            q.append(now)
            remaining = max(0, max_req - len(q))
            return True, remaining, 0

    def get_status(self, key: str, limit: int | None = None) -> tuple[int, int]:
        max_req = limit or self.max_requests
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._history[key]
            while q and q[0] < cutoff:
                q.popleft()
            remaining = max(0, max_req - len(q))
            reset_sec = max(1, int(q[0] + self.window_seconds - now)) if q else self.window_seconds
            return remaining, reset_sec

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


_sync_limiter = SyncAdapterRateLimiter()


def _user(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _sync_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    envelope = SyncAdapterErrorEnvelope(
        error_code=error_code,
        message=message,
        correlation_id=f"sync-err-{uuid4().hex[:12]}",
        details=details or {},
        timestamp=datetime.now(UTC),
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
        headers=headers,
    )


def _dto_to_canonical_batch(payload: SyncAdapterBatchRequestDTO) -> ConnectorImportBatch:
    canonical_records: list[CanonicalHealthRecord] = []
    for rec in payload.records:
        device_dict = rec.device or {}
        device = ConnectorDevice(
            manufacturer=str(device_dict.get("manufacturer", "")),
            model=str(device_dict.get("model", "")),
            type=str(device_dict.get("type", "unknown")),
        )
        quality_dict = rec.quality or {}
        quality = ConnectorQuality(
            state=quality_dict.get("state", "source_asserted"),
            flags=quality_dict.get("flags", []),
        )
        prov_dict = rec.provenance or {}
        provenance = ConnectorProvenance(
            adapter_version=str(prov_dict.get("adapter_version", "1.0")),
            raw_hash=str(prov_dict.get("raw_hash", "sha256:" + "0" * 64)),
        )
        val = CanonicalHealthValue(
            scalar=rec.value.scalar,
            components=rec.value.components,
            unit=rec.value.unit,
        )
        canonical_records.append(
            CanonicalHealthRecord(
                schema_version=rec.schema_version,
                profile_id=rec.profile_id,
                connector_id=rec.connector_id,
                provider=ConnectorProvider(rec.provider),
                provider_record_id=rec.provider_record_id,
                record_type=HealthRecordType(rec.record_type),
                value=val,
                observed_start=rec.observed_start,
                observed_end=rec.observed_end,
                zone_offset_start=rec.zone_offset_start,
                zone_offset_end=rec.zone_offset_end,
                data_origin=rec.data_origin,
                device=device,
                recording_method=RecordingMethod(rec.recording_method)
                if rec.recording_method in [m.value for m in RecordingMethod]
                else RecordingMethod.UNKNOWN,
                quality=quality,
                provenance=provenance,
            )
        )

    canonical_tombstones = [
        ConnectorRecordTombstone(
            provider_record_id=t.provider_record_id,
            data_origin=t.data_origin,
            deleted_at=t.deleted_at,
        )
        for t in payload.tombstones
    ]

    return ConnectorImportBatch(
        schema_version="1.0",
        idempotency_key=payload.idempotency_key,
        profile_id=payload.profile_id,
        connector_id=payload.connector_id,
        provider=ConnectorProvider(payload.provider),
        cursor=payload.cursor,
        records=canonical_records,
        tombstones=canonical_tombstones,
    )


def _process_sync_adapter_batch(
    connector_id: int,
    payload: SyncAdapterBatchRequestDTO,
    db: Session,
    user: User,
    x_idempotency_key: str | None = None,
) -> Response:
    # 1. Rate Limiting Check
    rate_key = f"connector:{connector_id}"
    allowed, remaining, retry_after = _sync_limiter.check_and_record(rate_key)
    if not allowed:
        return _sync_error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            message=f"Tần suất đồng bộ vượt quá giới hạn cho phép (60 yêu cầu/phút). Vui lòng thử lại sau {retry_after} giây.",
            details={"retry_after_seconds": retry_after, "limit": 60, "connector_id": str(connector_id)},
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "0",
            },
        )

    # 2. Payload Bounds Validation (WH-067 payload bomb protection)
    if len(payload.records) > 500 or len(payload.tombstones) > 500:
        return _sync_error_response(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code="PAYLOAD_TOO_LARGE",
            message="Kích thước lô đồng bộ vượt quá giới hạn tối đa 500 bản ghi/tombstone.",
            details={"records_count": len(payload.records), "tombstones_count": len(payload.tombstones), "max_allowed": 500},
        )

    # 3. Idempotency Key Alignment
    if x_idempotency_key and payload.idempotency_key != x_idempotency_key:
        return _sync_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="IDEMPOTENCY_KEY_MISMATCH",
            message="X-Idempotency-Key tiêu đề không khớp với idempotency_key trong payload.",
            details={"header_key": x_idempotency_key, "body_key": payload.idempotency_key},
        )

    # 4. Connector Ownership & Existence Check
    try:
        connector = owned_connector(db, connector_id=connector_id, user=user)
    except HTTPException as exc:
        return _sync_error_response(
            status_code=exc.status_code,
            error_code="CONNECTOR_NOT_FOUND",
            message="Thiết bị kết nối không tồn tại hoặc không thuộc quyền sở hữu của người dùng.",
            details={"connector_id": str(connector_id)},
        )

    # 5. Connector Status Check
    if connector.status not in {"connected", "healthy"}:
        return _sync_error_response(
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONNECTOR_NOT_READY",
            message=f"Thiết bị kết nối đang ở trạng thái '{connector.status}', không sẵn sàng đồng bộ dữ liệu.",
            details={"status": connector.status, "connector_id": str(connector_id)},
        )

    # 6. Profile Scope & Provider Validation
    if payload.connector_id != str(connector.id) or payload.profile_id != str(connector.profile_id):
        return _sync_error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="SCOPE_MISMATCH",
            message="Phạm vi hồ sơ người dùng hoặc mã kết nối không khớp với quyền được cấp.",
            details={"expected_profile": str(connector.profile_id), "provided_profile": payload.profile_id},
        )

    if payload.provider != connector.provider:
        return _sync_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="PROVIDER_MISMATCH",
            message=f"Nhà cung cấp '{payload.provider}' không khớp với loại kết nối '{connector.provider}'.",
            details={"expected_provider": connector.provider, "provided_provider": payload.provider},
        )

    # 7. Active Consent Check
    consent = active_consent(db, connector_id=connector.id)
    if consent is None:
        return _sync_error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="CONSENT_REVOKED",
            message="Người dùng đã rút lại sự đồng ý cho kết nối dữ liệu thiết bị này.",
            details={"connector_id": str(connector_id)},
        )

    # 8. Conversion to canonical batch & ingestion
    try:
        canonical_batch = _dto_to_canonical_batch(payload)
    except ValueError as val_err:
        return _sync_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_PAYLOAD",
            message=f"Dữ liệu bản ghi không hợp lệ: {val_err}",
            details={"error": str(val_err)},
        )

    try:
        import_res = import_batch(
            db,
            connector=connector,
            user=user,
            payload=canonical_batch,
        )
    except HTTPException as exc:
        code_map = {
            409: "IDEMPOTENCY_CONFLICT",
            403: "CONSENT_RESTRICTION",
            422: "INVALID_RECORD_FORMAT",
        }
        err_code = code_map.get(exc.status_code, "SYNC_IMPORT_FAILED")
        return _sync_error_response(
            status_code=exc.status_code,
            error_code=err_code,
            message=str(exc.detail),
            details={"http_status": exc.status_code},
        )

    # 9. Formulate Success Response
    now_utc = datetime.now(UTC)
    response_dto = SyncAdapterBatchResponseDTO(
        protocol_version="connector.sync.v1",
        batch_id=str(import_res.batch_id),
        status="IDEMPOTENT_REPLAY" if import_res.idempotent_replay else "COMMITTED",
        idempotent_replay=import_res.idempotent_replay,
        accepted_count=import_res.accepted_count,
        rejected_count=import_res.rejected_count,
        upserted_count=import_res.upserted_count,
        tombstoned_count=import_res.tombstoned_count,
        next_cursor=payload.cursor,
        watermark=now_utc,
        errors=[],
        rate_limit_status=SyncRateLimitStatusDTO(
            remaining=remaining,
            limit=60,
            reset_seconds=60,
        ),
        server_time=now_utc,
    )

    headers = {
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": str(remaining),
        "X-Idempotent-Replay": "true" if import_res.idempotent_replay else "false",
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_dto.model_dump(mode="json"), headers=headers)


@router.get("/capabilities", response_model=list[ConnectorCapabilityResponse])
def capabilities(
    _token: TokenPayload = USER_ROLE_DEP,
) -> list[ConnectorCapabilityResponse]:
    return _CAPABILITIES


@router.get("/sync/protocol", response_model=SyncAdapterProtocolHandshakeResponse)
def get_sync_protocol(
    _token: TokenPayload = USER_ROLE_DEP,
) -> SyncAdapterProtocolHandshakeResponse:
    """Return protocol capabilities, rate limits, and idempotency rules for sync adapters."""
    return SyncAdapterProtocolHandshakeResponse(
        server_time=datetime.now(UTC),
    )


@router.get("", response_model=list[ConnectorResponse])
def list_connectors(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> list[ConnectorResponse]:
    user = _user(db, token)
    connectors = db.execute(
        select(ConnectorAccount)
        .where(ConnectorAccount.user_id == user.id)
        .order_by(ConnectorAccount.id)
    ).scalars()
    return [serialize_connector(db, connector) for connector in connectors]


@router.post("/device", response_model=ConnectorResponse, status_code=201)
def create_device(
    payload: DeviceConnectorCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ConnectorResponse:
    return create_device_connector(db, user=_user(db, token), payload=payload)


@router.post("/{connector_id}/imports", response_model=ConnectorImportResponse)
def import_connector_records(
    connector_id: int,
    payload: ConnectorImportBatch,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ConnectorImportResponse:
    rate_key = f"connector:{connector_id}"
    allowed, remaining, retry_after = _sync_limiter.check_and_record(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    user = _user(db, token)
    return import_batch(
        db,
        connector=owned_connector(db, connector_id=connector_id, user=user),
        user=user,
        payload=payload,
    )


@router.post("/{connector_id}/sync/adapter", response_model=SyncAdapterBatchResponseDTO)
def sync_adapter_batch(
    connector_id: int,
    payload: SyncAdapterBatchRequestDTO,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
) -> Response:
    """Submit a batch of normalized health records via sync adapter protocol."""
    user = _user(db, token)
    return _process_sync_adapter_batch(
        connector_id=connector_id,
        payload=payload,
        db=db,
        user=user,
        x_idempotency_key=x_idempotency_key,
    )


@router.post("/sync/batch", response_model=SyncAdapterBatchResponseDTO)
def sync_adapter_batch_body(
    payload: SyncAdapterBatchRequestDTO,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
) -> Response:
    """Body-addressed endpoint for sync adapter batch submission."""
    user = _user(db, token)
    try:
        conn_id = int(payload.connector_id)
    except ValueError:
        return _sync_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_CONNECTOR_ID",
            message="Mã kết nối connector_id phải là số nguyên hợp lệ.",
            details={"connector_id": payload.connector_id},
        )
    return _process_sync_adapter_batch(
        connector_id=conn_id,
        payload=payload,
        db=db,
        user=user,
        x_idempotency_key=x_idempotency_key,
    )


@router.get("/{connector_id}/sync/status", response_model=SyncAdapterCursorResponseDTO)
def get_connector_sync_status(
    connector_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> SyncAdapterCursorResponseDTO:
    """Query synchronization state, active cursor, and watermark for a connector."""
    user = _user(db, token)
    connector = owned_connector(db, connector_id=connector_id, user=user)

    cursor_record = db.execute(
        select(ConnectorSyncCursor)
        .where(ConnectorSyncCursor.connector_id == connector.id)
        .order_by(ConnectorSyncCursor.updated_at.desc())
    ).scalars().first()

    return SyncAdapterCursorResponseDTO(
        connector_id=str(connector.id),
        provider=str(connector.provider),
        status=connector.status,
        active_cursor=cursor_record.cursor if cursor_record else None,
        last_sync_watermark=cursor_record.window_end if cursor_record else None,
        last_synced_at=connector.last_synced_at,
        uncommitted_records_pending=False,
    )


@router.post("/{connector_id}/sync/ack", response_model=SyncAdapterCursorAckResponseDTO)
def ack_connector_cursor(
    connector_id: int,
    payload: SyncAdapterCursorAckRequestDTO,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> SyncAdapterCursorAckResponseDTO:
    """Acknowledge cursor commitment by the client adapter."""
    user = _user(db, token)
    connector = owned_connector(db, connector_id=connector_id, user=user)

    if str(connector.id) != payload.connector_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload connector_id does not match path parameter",
        )

    now_utc = datetime.now(UTC)
    cursor_rec = db.execute(
        select(ConnectorSyncCursor).where(ConnectorSyncCursor.connector_id == connector.id)
    ).scalars().first()

    if cursor_rec is None:
        cursor_rec = ConnectorSyncCursor(
            connector_id=connector.id,
            data_type="all",
            cursor=payload.committed_cursor,
            window_end=now_utc,
            updated_at=now_utc,
        )
        db.add(cursor_rec)
    else:
        cursor_rec.cursor = payload.committed_cursor
        cursor_rec.window_end = now_utc
        cursor_rec.updated_at = now_utc

    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.cursor_acknowledged",
        metadata={
            "committed_cursor": payload.committed_cursor,
            "records_processed": payload.records_processed,
        },
    )
    db.commit()

    return SyncAdapterCursorAckResponseDTO(
        connector_id=str(connector.id),
        acknowledged=True,
        updated_cursor=payload.committed_cursor,
        server_time=now_utc,
    )


@router.post("/{connector_id}/sync", response_model=ConnectorOperationResponse)
def sync_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ConnectorOperationResponse:
    user = _user(db, token)
    return request_sync(
        db,
        connector=owned_connector(db, connector_id=connector_id, user=user),
        user=user,
    )


@router.post("/{connector_id}/pause", response_model=ConnectorResponse)
def pause_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ConnectorResponse:
    user = _user(db, token)
    return transition(
        db,
        connector=owned_connector(db, connector_id=connector_id, user=user),
        user=user,
        target="paused",
    )


@router.post("/{connector_id}/resume", response_model=ConnectorResponse)
def resume_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ConnectorResponse:
    user = _user(db, token)
    return transition(
        db,
        connector=owned_connector(db, connector_id=connector_id, user=user),
        user=user,
        target="connected",
    )


@router.delete("/{connector_id}", response_model=ConnectorResponse)
def disconnect_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ConnectorResponse:
    user = _user(db, token)
    return disconnect(
        db,
        connector=owned_connector(db, connector_id=connector_id, user=user),
        user=user,
    )


@router.delete(
    "/{connector_id}/imported-data",
    response_model=ImportedDataDeletionResponse,
)
def remove_imported_data(
    connector_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ImportedDataDeletionResponse:
    user = _user(db, token)
    return delete_imported_data(
        db,
        connector=owned_connector(db, connector_id=connector_id, user=user),
        user=user,
    )


@router.get("/status-adapter", response_model=dict[str, Any])
def connector_status_adapter(
    db: Session = Depends(get_db),
    _token: TokenPayload = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """Admin adapter returning aggregate connector status and outbox health."""
    active_count = db.query(ConnectorAccount).filter(ConnectorAccount.status == "connected").count()
    paused_count = db.query(ConnectorAccount).filter(ConnectorAccount.status == "paused").count()
    total_count = db.query(ConnectorAccount).count()
    return {
        "status": "healthy",
        "total_connectors": total_count,
        "active_connectors": active_count,
        "paused_connectors": paused_count,
        "outbox_adapter_linked": True,
    }
