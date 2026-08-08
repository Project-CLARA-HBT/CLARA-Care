"""Atomic canonical-record ingestion for consented device imports."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from clara_api.connected_health.control import ConnectorImportResponse
from clara_api.connected_health.projection import recompute_steps_daily_aggregates
from clara_api.connected_health.schemas import ConnectorImportBatch as ImportPayload
from clara_api.connected_health.service import active_consent, audit
from clara_api.db.models import (
    ConnectorAccount,
    ConnectorImportBatch,
    ConnectorSyncCursor,
    PhrProfile,
    User,
    WearableObservation,
    WearableObservationVersion,
)
from clara_api.glhs.adapters import ingest_connected_health_observation, owner_profile_scope


def _payload_hash(payload: ImportPayload) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _snapshot(observation: WearableObservation) -> dict:
    return {
        "value": observation.value_json,
        "observed_start": observation.observed_start.isoformat(),
        "observed_end": observation.observed_end.isoformat(),
        "device": observation.device_json,
        "recording_method": observation.recording_method,
        "quality": observation.quality_json,
        "provenance": observation.provenance_json,
        "provider_updated_at": (
            observation.provider_updated_at.isoformat()
            if observation.provider_updated_at is not None
            else None
        ),
        "raw_hash": observation.raw_hash,
        "is_active": observation.is_active,
        "deleted_at": observation.deleted_at.isoformat() if observation.deleted_at else None,
    }


def _response(batch: ConnectorImportBatch, *, replay: bool) -> ConnectorImportResponse:
    return ConnectorImportResponse(
        batch_id=str(batch.id),
        idempotent_replay=replay,
        accepted_count=batch.accepted_count,
        rejected_count=batch.rejected_count,
        upserted_count=batch.upserted_count,
        tombstoned_count=batch.tombstoned_count,
    )


def import_batch(
    db: Session,
    *,
    connector: ConnectorAccount,
    user: User,
    payload: ImportPayload,
) -> ConnectorImportResponse:
    """Validate and durably apply one provider page without partial cursor progress."""

    if connector.status not in {"connected", "healthy"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connector is not available for imports",
        )
    if payload.connector_id != str(connector.id) or payload.profile_id != str(connector.profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Import scope mismatch",
        )
    if payload.provider.value != connector.provider:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provider mismatch",
        )

    consent = active_consent(db, connector_id=connector.id)
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Connector consent revoked",
        )
    consent_types = consent.data_types_json if isinstance(consent.data_types_json, list) else []
    granted_types = set(consent_types)
    requested_types = {record.record_type.value for record in payload.records}
    if not requested_types.issubset(granted_types):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Import includes unconsented data type",
        )

    digest = _payload_hash(payload)
    previous = db.execute(
        select(ConnectorImportBatch).where(
            ConnectorImportBatch.connector_id == connector.id,
            ConnectorImportBatch.idempotency_key == payload.idempotency_key,
        )
    ).scalar_one_or_none()
    if previous is not None:
        if previous.payload_hash != digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for another payload",
            )
        return _response(previous, replay=True)

    batch = ConnectorImportBatch(
        connector_id=connector.id,
        profile_id=connector.profile_id,
        idempotency_key=payload.idempotency_key,
        payload_hash=digest,
        status="processing",
    )
    db.add(batch)
    db.flush()
    accepted = upserted = tombstoned = 0
    affected_steps_dates = set()

    for record in payload.records:
        current = db.execute(
            select(WearableObservation).where(
                WearableObservation.connector_id == connector.id,
                WearableObservation.data_origin == record.data_origin,
                WearableObservation.provider_record_id == record.provider_record_id,
            )
        ).scalar_one_or_none()
        if current is None:
            current = WearableObservation(
                profile_id=connector.profile_id,
                connector_id=connector.id,
                provider=connector.provider,
                provider_record_id=record.provider_record_id,
                data_origin=record.data_origin,
                record_type=record.record_type.value,
                value_json=record.value.model_dump(mode="json"),
                observed_start=record.observed_start,
                observed_end=record.observed_end,
                zone_offset_start=record.zone_offset_start,
                zone_offset_end=record.zone_offset_end,
                device_json=record.device.model_dump(mode="json"),
                recording_method=record.recording_method.value,
                quality_json=record.quality.model_dump(mode="json"),
                provenance_json=record.provenance.model_dump(mode="json"),
                provider_updated_at=record.provider_updated_at,
                raw_hash=record.provenance.raw_hash,
                is_active=True,
            )
            db.add(current)
            upserted += 1
        elif current.raw_hash != record.provenance.raw_hash or not current.is_active:
            if current.record_type == "steps":
                affected_steps_dates.add(current.observed_start.date())
            db.add(
                WearableObservationVersion(
                    observation_id=current.id,
                    version_no=current.version_no,
                    snapshot_json=_snapshot(current),
                )
            )
            current.value_json = record.value.model_dump(mode="json")
            current.observed_start = record.observed_start
            current.observed_end = record.observed_end
            current.zone_offset_start = record.zone_offset_start
            current.zone_offset_end = record.zone_offset_end
            current.device_json = record.device.model_dump(mode="json")
            current.recording_method = record.recording_method.value
            current.quality_json = record.quality.model_dump(mode="json")
            current.provenance_json = record.provenance.model_dump(mode="json")
            current.provider_updated_at = record.provider_updated_at
            current.raw_hash = record.provenance.raw_hash
            current.version_no += 1
            current.is_active = True
            current.deleted_at = None
            upserted += 1
        accepted += 1
        if record.record_type.value == "steps":
            affected_steps_dates.add(record.observed_start.date())

    for tombstone in payload.tombstones:
        current = db.execute(
            select(WearableObservation).where(
                WearableObservation.connector_id == connector.id,
                WearableObservation.data_origin == tombstone.data_origin,
                WearableObservation.provider_record_id == tombstone.provider_record_id,
            )
        ).scalar_one_or_none()
        if current is not None and current.is_active:
            db.add(
                WearableObservationVersion(
                    observation_id=current.id,
                    version_no=current.version_no,
                    snapshot_json=_snapshot(current),
                )
            )
            current.version_no += 1
            current.is_active = False
            current.deleted_at = tombstone.deleted_at
            tombstoned += 1
            if current.record_type == "steps":
                affected_steps_dates.add(current.observed_start.date())

    db.flush()
    # Connected-health rows are provider evidence, not clinician-confirmed
    # health state. Mirror their active/update/tombstone semantics through the
    # API-owned GLHS adapter before committing the connector cursor.
    profile = db.get(PhrProfile, connector.profile_id)
    if profile is None:  # connector ownership should make this unreachable
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connector profile missing",
        )
    scope = owner_profile_scope(profile=profile, actor=user)
    affected_keys = [
        (record.data_origin, record.provider_record_id) for record in payload.records
    ] + [
        (tombstone.data_origin, tombstone.provider_record_id)
        for tombstone in payload.tombstones
    ]
    affected_selectors = [
        and_(
            WearableObservation.data_origin == data_origin,
            WearableObservation.provider_record_id == provider_record_id,
        )
        for data_origin, provider_record_id in affected_keys
    ]
    affected_records = list(
        db.execute(
            select(WearableObservation).where(
                WearableObservation.connector_id == connector.id,
                WearableObservation.profile_id == connector.profile_id,
                or_(*affected_selectors),
            )
        ).scalars()
    )
    for observation in affected_records:
        ingest_connected_health_observation(
            db,
            scope=scope,
            observation=observation,
            idempotency_key=payload.idempotency_key,
        )
    if affected_steps_dates:
        recompute_steps_daily_aggregates(
            db,
            profile_id=connector.profile_id,
            affected_dates=affected_steps_dates,
        )

    if payload.cursor is not None:
        for record_type in requested_types:
            cursor = db.execute(
                select(ConnectorSyncCursor).where(
                    ConnectorSyncCursor.connector_id == connector.id,
                    ConnectorSyncCursor.data_type == record_type,
                )
            ).scalar_one_or_none()
            if cursor is None:
                db.add(
                    ConnectorSyncCursor(
                        connector_id=connector.id,
                        data_type=record_type,
                        cursor=payload.cursor,
                    )
                )
            else:
                cursor.cursor = payload.cursor

    now = datetime.now(UTC)
    batch.status = "committed"
    batch.accepted_count = accepted
    batch.rejected_count = 0
    batch.upserted_count = upserted
    batch.tombstoned_count = tombstoned
    batch.committed_at = now
    connector.status = "healthy"
    connector.last_synced_at = now
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.import_committed",
        metadata={
            "accepted_count": accepted,
            "upserted_count": upserted,
            "tombstoned_count": tombstoned,
        },
    )
    db.commit()
    db.refresh(batch)
    return _response(batch, replay=False)
