"""Connected-health connector control plane."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.connected_health.control import (
    ConnectorCapabilityResponse,
    ConnectorOperationResponse,
    ConnectorResponse,
    DeviceConnectorCreateRequest,
    ImportedDataDeletionResponse,
)
from clara_api.connected_health.schemas import ConnectorProvider, HealthRecordType
from clara_api.connected_health.service import (
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
from clara_api.db.models import ConnectorAccount, User
from clara_api.db.session import get_db

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


def _user(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.get("/capabilities", response_model=list[ConnectorCapabilityResponse])
def capabilities(
    _token: TokenPayload = USER_ROLE_DEP,
) -> list[ConnectorCapabilityResponse]:
    return _CAPABILITIES


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
