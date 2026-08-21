"""Profile-scoped connected-health control-plane operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from clara_api.connected_health.control import (
    ConnectorOperationResponse,
    ConnectorProvider,
    ConnectorPurpose,
    ConnectorResponse,
    DeviceConnectorCreateRequest,
    HealthRecordType,
    ImportedDataDeletionResponse,
)
from clara_api.db.models import (
    ConnectorAccount,
    ConnectorAuditEvent,
    ConnectorConsent,
    PhrProfile,
    User,
    WearableAggregateContribution,
    WearableDailyAggregate,
    WearableObservation,
)

_PAUSABLE_STATES = {"connected", "healthy", "needs_reauth", "error"}


def get_or_create_profile(db: Session, *, user: User) -> PhrProfile:
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        profile = PhrProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def owned_connector(db: Session, *, connector_id: int, user: User) -> ConnectorAccount:
    connector = db.execute(
        select(ConnectorAccount).where(
            ConnectorAccount.id == connector_id,
            ConnectorAccount.user_id == user.id,
        )
    ).scalar_one_or_none()
    if connector is None:
        # Deliberately do not reveal whether another profile owns this ID.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    return connector


def active_consent(db: Session, *, connector_id: int) -> ConnectorConsent | None:
    return db.execute(
        select(ConnectorConsent)
        .where(
            ConnectorConsent.connector_id == connector_id,
            ConnectorConsent.revoked_at.is_(None),
        )
        .order_by(ConnectorConsent.id.desc())
    ).scalars().first()


def serialize_connector(db: Session, connector: ConnectorAccount) -> ConnectorResponse:
    consent = active_consent(db, connector_id=connector.id)
    raw_data_types = connector.data_types_json
    data_types = raw_data_types if isinstance(raw_data_types, list) else []
    raw_purposes = consent.purposes_json if consent is not None else []
    purposes = raw_purposes if isinstance(raw_purposes, list) else []
    return ConnectorResponse(
        id=str(connector.id),
        provider=cast(ConnectorProvider, connector.provider),
        display_label=connector.display_label,
        status=connector.status,
        data_types=cast(list[HealthRecordType], data_types),
        purposes=cast(list[ConnectorPurpose], purposes),
        last_synced_at=connector.last_synced_at,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


def audit(
    db: Session,
    *,
    connector: ConnectorAccount,
    actor_user_id: int,
    event_type: str,
    purpose: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        ConnectorAuditEvent(
            connector_id=connector.id,
            profile_id=connector.profile_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            purpose=purpose,
            metadata_json=metadata,
        )
    )


def create_device_connector(
    db: Session,
    *,
    user: User,
    payload: DeviceConnectorCreateRequest,
) -> ConnectorResponse:
    profile = get_or_create_profile(db, user=user)
    provider = payload.provider.value
    connector = db.execute(
        select(ConnectorAccount).where(
            ConnectorAccount.profile_id == profile.id,
            ConnectorAccount.provider == provider,
            ConnectorAccount.external_subject_ref == payload.external_subject_ref,
        )
    ).scalar_one_or_none()
    if connector is not None and connector.status != "disconnected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This health source is already connected",
        )

    data_types = [item.value for item in payload.data_types]
    purposes = list(payload.purposes)
    if connector is None:
        connector = ConnectorAccount(
            user_id=user.id,
            profile_id=profile.id,
            provider=provider,
            external_subject_ref=payload.external_subject_ref,
        )
        db.add(connector)
        db.flush()

    connector.display_label = payload.display_label.strip()
    connector.status = "connected"
    connector.scopes_json = ["read"]
    connector.data_types_json = data_types
    connector.token_ciphertext = None
    connector.token_key_version = None

    db.add(
        ConnectorConsent(
            connector_id=connector.id,
            user_id=user.id,
            consent_version=payload.consent_version,
            purposes_json=purposes,
            data_types_json=data_types,
            access_direction="read",
        )
    )
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.authorized",
        metadata={"provider": provider, "data_type_count": len(data_types)},
    )
    db.commit()
    db.refresh(connector)
    return serialize_connector(db, connector)


def transition(
    db: Session,
    *,
    connector: ConnectorAccount,
    user: User,
    target: str,
) -> ConnectorResponse:
    current = connector.status
    if target == "paused" and current not in _PAUSABLE_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector cannot transition from {current} to paused",
        )
    if target == "connected" and current != "paused":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector cannot transition from {current} to connected",
        )

    connector.status = target
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type=f"connector.{target}",
        metadata={"previous_status": current},
    )
    db.commit()
    db.refresh(connector)
    return serialize_connector(db, connector)


def request_sync(
    db: Session,
    *,
    connector: ConnectorAccount,
    user: User,
) -> ConnectorOperationResponse:
    if connector.status == "paused":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connector is paused")
    if connector.status in {"disconnected", "revoked"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connector must be reauthorized before sync",
        )
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.sync_requested",
    )
    db.commit()
    return ConnectorOperationResponse(
        connector=serialize_connector(db, connector),
        action="device_import_required",
    )


def disconnect(
    db: Session,
    *,
    connector: ConnectorAccount,
    user: User,
) -> ConnectorResponse:
    if connector.status == "disconnected":
        return serialize_connector(db, connector)

    now = datetime.now(UTC)
    for consent in db.execute(
        select(ConnectorConsent).where(
            ConnectorConsent.connector_id == connector.id,
            ConnectorConsent.revoked_at.is_(None),
        )
    ).scalars():
        consent.revoked_at = now
    previous = connector.status
    connector.status = "disconnected"
    connector.token_ciphertext = None
    connector.token_key_version = None
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.disconnected",
        metadata={"previous_status": previous, "imported_data_preserved": True},
    )
    db.commit()
    db.refresh(connector)
    return serialize_connector(db, connector)


def delete_imported_data(
    db: Session,
    *,
    connector: ConnectorAccount,
    user: User,
) -> ImportedDataDeletionResponse:
    observation_ids = list(
        db.execute(
            select(WearableObservation.id).where(
                WearableObservation.connector_id == connector.id
            )
        ).scalars()
    )
    aggregate_ids: set[int] = set()
    if observation_ids:
        aggregate_ids = set(
            db.execute(
                select(WearableAggregateContribution.aggregate_id).where(
                    WearableAggregateContribution.observation_id.in_(observation_ids)
                )
            ).scalars()
        )
        db.execute(
            delete(WearableObservation).where(
                WearableObservation.connector_id == connector.id
            )
        )
    if aggregate_ids:
        # Aggregates are projections, so invalidate rather than retain a value
        # that may have depended on the deleted source.
        db.execute(
            delete(WearableDailyAggregate).where(
                WearableDailyAggregate.id.in_(aggregate_ids)
            )
        )
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.imported_data_deleted",
        metadata={
            "deleted_observation_count": len(observation_ids),
            "invalidated_aggregate_count": len(aggregate_ids),
        },
    )
    db.commit()
    return ImportedDataDeletionResponse(
        connector_id=str(connector.id),
        deleted_observations=len(observation_ids),
        invalidated_aggregates=len(aggregate_ids),
    )
