"""Canonical Connected Observation Envelope and Deduplication Engine.

Provides versioned canonical contracts and idempotent ingestion pipelines for
external health and wearable sources (Health Connect, Apple Health, Dexcom, Fitbit).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    ConnectorAccount,
    PhrProfile,
    User,
    WearableObservation,
    WearableObservationVersion,
)

SUPPORTED_SOURCE_SYSTEMS: frozenset[str] = frozenset(
    {"health_connect", "apple_health", "dexcom", "fitbit"}
)

SUPPORTED_DATA_TYPES: frozenset[str] = frozenset(
    {
        "steps",
        "sleep",
        "heart_rate",
        "blood_pressure",
        "oxygen_saturation",
        "body_weight",
        "blood_glucose",
    }
)

SourceSystemType = Literal["health_connect", "apple_health", "dexcom", "fitbit"]
DataType = Literal[
    "steps",
    "sleep",
    "heart_rate",
    "blood_pressure",
    "oxygen_saturation",
    "body_weight",
    "blood_glucose",
]


class ConnectedObservationEnvelope(BaseModel):
    """Canonical observation envelope for all connected health integrations."""

    model_config = ConfigDict(extra="ignore")

    profile_id: int = Field(..., description="Target profile ID")
    source_system: str = Field(
        ...,
        description=(
            "Originating connector system: 'health_connect', 'apple_health', "
            "'dexcom', or 'fitbit'"
        ),
    )
    source_record_id: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Source system record identifier",
    )
    source_device_id: str | None = Field(
        default=None,
        description="Optional hardware/device identifier",
    )
    data_type: str = Field(
        ...,
        description=(
            "Normalized metric type: 'steps', 'sleep', 'heart_rate', "
            "'blood_pressure', 'oxygen_saturation', 'body_weight', 'blood_glucose'"
        ),
    )
    effective_start: datetime = Field(
        ...,
        description="Start timestamp of measurement or observation interval",
    )
    effective_end: datetime | None = Field(
        default=None,
        description="End timestamp for interval measurements (optional)",
    )
    observed_value: dict[str, Any] = Field(
        ...,
        description="Structured observation value dictionary",
    )
    unit: str | None = Field(
        default=None,
        max_length=64,
        description="Standard measurement unit (e.g. 'count', 'beats/min', 'mm[Hg]', 'mg/dL')",
    )
    source_version: str | None = Field(
        default=None,
        max_length=64,
        description="Source-side revision or state version string",
    )
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Server ingestion timestamp",
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Provenance metadata such as app id, sensor flags, or sync session",
    )

    @field_validator("source_system")
    @classmethod
    def validate_source_system(cls, value: str) -> str:
        clean = value.strip().lower()
        if clean not in SUPPORTED_SOURCE_SYSTEMS:
            allowed = sorted(SUPPORTED_SOURCE_SYSTEMS)
            raise ValueError(f"Invalid source_system '{value}'. Must be one of: {allowed}")
        return clean

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, value: str) -> str:
        clean = value.strip().lower()
        if clean not in SUPPORTED_DATA_TYPES:
            allowed = sorted(SUPPORTED_DATA_TYPES)
            raise ValueError(f"Invalid data_type '{value}'. Must be one of: {allowed}")
        return clean

    @field_validator("effective_start", "effective_end", "ingested_at")
    @classmethod
    def ensure_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> ConnectedObservationEnvelope:
        if self.effective_end is not None and self.effective_end < self.effective_start:
            raise ValueError("effective_end cannot precede effective_start")
        return self

    @property
    def deduplication_key(self) -> str:
        """Deterministic deduplication key for this envelope."""
        return compute_deduplication_key(self)

    @property
    def payload_hash(self) -> str:
        """SHA-256 hash of canonical observation payload."""
        return compute_envelope_hash(self)


def compute_deduplication_key(envelope: ConnectedObservationEnvelope) -> str:
    """Compute deterministic deduplication key for a connected observation envelope.

    Includes source system + profile + source record identity + version to ensure
    no duplicate events are created on retry while allowing explicit version updates.
    """
    version_part = envelope.source_version or "v1"
    return (
        f"{envelope.profile_id}:{envelope.source_system}:"
        f"{envelope.source_record_id}:{version_part}"
    )


def compute_envelope_hash(envelope: ConnectedObservationEnvelope) -> str:
    """Compute SHA-256 hash of canonical observation payload content."""
    canonical_payload = {
        "profile_id": envelope.profile_id,
        "source_system": envelope.source_system,
        "source_record_id": envelope.source_record_id,
        "data_type": envelope.data_type,
        "effective_start": envelope.effective_start.isoformat(),
        "effective_end": envelope.effective_end.isoformat() if envelope.effective_end else None,
        "observed_value": envelope.observed_value,
        "unit": envelope.unit,
        "source_version": envelope.source_version,
    }
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class DeduplicationResult(BaseModel):
    """Result of an observation deduplication & ingestion evaluation."""

    model_config = ConfigDict(extra="ignore")

    is_duplicate: bool = Field(description="True if identical record was already processed")
    deduplication_key: str = Field(description="Deterministic deduplication key")
    record_hash: str = Field(description="SHA-256 digest of payload")
    action_taken: Literal["created", "updated", "deduplicated_noop"] | str = Field(
        description="Action performed: created, updated, or deduplicated_noop"
    )
    observation_id: int | None = Field(
        default=None, description="Observation ID in the database"
    )


class EnvelopeDeduplicator:
    """In-memory deduplication tracker for testing and stream deduplication."""

    def __init__(self) -> None:
        self._seen_keys: dict[str, str] = {}

    def is_duplicate(self, envelope: ConnectedObservationEnvelope) -> bool:
        """Check if envelope has been seen with identical payload."""
        key = compute_deduplication_key(envelope)
        digest = compute_envelope_hash(envelope)
        if key in self._seen_keys and self._seen_keys[key] == digest:
            return True
        self._seen_keys[key] = digest
        return False

    def clear(self) -> None:
        self._seen_keys.clear()


def ingest_observation_envelope(
    db: Session,
    envelope: ConnectedObservationEnvelope,
    *,
    user: User | None = None,
) -> DeduplicationResult:
    """Deduplicate and durably ingest a single ConnectedObservationEnvelope.

    Guarantees:
    - Exactly-once ingestion on retries: identical envelope re-sends produce deduplicated_noop.
    - Updated values/versions create an immutable version snapshot before mutation.
    - Auto-provisions or reuses ConnectorAccount for the profile and source system.
    """
    now = datetime.now(UTC)

    # 1. Resolve Profile and Account Owner
    profile = db.get(PhrProfile, envelope.profile_id)
    if profile is None:
        raise ValueError(f"Target profile {envelope.profile_id} does not exist")

    user_id = user.id if user else profile.user_id

    # 2. Resolve or provision ConnectorAccount
    connector = db.execute(
        select(ConnectorAccount).where(
            ConnectorAccount.profile_id == envelope.profile_id,
            ConnectorAccount.provider == envelope.source_system,
        )
    ).scalars().first()

    if connector is None:
        connector = ConnectorAccount(
            user_id=user_id,
            profile_id=envelope.profile_id,
            provider=envelope.source_system,
            external_subject_ref=f"{envelope.source_system}_sub_{envelope.profile_id}",
            display_label=envelope.source_system.replace("_", " ").title(),
            status="connected",
            scopes_json=[envelope.data_type],
            data_types_json=[envelope.data_type],
            last_synced_at=now,
        )
        db.add(connector)
        db.flush()
    else:
        # Ensure status is connected and data type is tracked
        if connector.status in {"available", "disconnected"}:
            connector.status = "connected"
        raw_types = connector.data_types_json
        types_list = raw_types if isinstance(raw_types, list) else []
        if envelope.data_type not in types_list:
            connector.data_types_json = list(types_list) + [envelope.data_type]

    # 3. Compute deduplication parameters
    dedup_key = compute_deduplication_key(envelope)
    current_hash = compute_envelope_hash(envelope)

    # 4. Check for existing observation by connector + provider_record_id
    existing_obs = db.execute(
        select(WearableObservation).where(
            WearableObservation.connector_id == connector.id,
            WearableObservation.provider_record_id == envelope.source_record_id,
        )
    ).scalars().first()

    if existing_obs is not None:
        # Duplicate detection: identical raw_hash and active state
        if existing_obs.raw_hash == current_hash and existing_obs.is_active:
            connector.last_synced_at = now
            return DeduplicationResult(
                is_duplicate=True,
                deduplication_key=dedup_key,
                record_hash=current_hash,
                action_taken="deduplicated_noop",
                observation_id=existing_obs.id,
            )

        # Record is updated / modified on retry with different version or payload:
        # Archive current state into WearableObservationVersion
        snapshot = {
            "value": existing_obs.value_json,
            "observed_start": existing_obs.observed_start.isoformat(),
            "observed_end": existing_obs.observed_end.isoformat(),
            "device": existing_obs.device_json,
            "recording_method": existing_obs.recording_method,
            "quality": existing_obs.quality_json,
            "provenance": existing_obs.provenance_json,
            "raw_hash": existing_obs.raw_hash,
            "is_active": existing_obs.is_active,
        }
        db.add(
            WearableObservationVersion(
                observation_id=existing_obs.id,
                version_no=existing_obs.version_no,
                snapshot_json=snapshot,
            )
        )

        # Mutate existing observation
        existing_obs.record_type = envelope.data_type
        existing_obs.value_json = envelope.observed_value
        existing_obs.observed_start = envelope.effective_start
        existing_obs.observed_end = envelope.effective_end or envelope.effective_start
        if envelope.source_device_id:
            existing_obs.device_json = {"device_id": envelope.source_device_id}
        existing_obs.provenance_json = envelope.provenance or {}
        existing_obs.raw_hash = current_hash
        existing_obs.version_no += 1
        existing_obs.is_active = True
        existing_obs.updated_at = now
        connector.last_synced_at = now
        db.flush()

        return DeduplicationResult(
            is_duplicate=False,
            deduplication_key=dedup_key,
            record_hash=current_hash,
            action_taken="updated",
            observation_id=existing_obs.id,
        )

    # 5. Insert brand new observation
    device_json = {"device_id": envelope.source_device_id} if envelope.source_device_id else None
    new_obs = WearableObservation(
        profile_id=envelope.profile_id,
        connector_id=connector.id,
        provider=envelope.source_system,
        provider_record_id=envelope.source_record_id,
        data_origin=envelope.source_system,
        record_type=envelope.data_type,
        value_json=envelope.observed_value,
        observed_start=envelope.effective_start,
        observed_end=envelope.effective_end or envelope.effective_start,
        device_json=device_json,
        recording_method="automatic",
        quality_json={"state": "source_asserted"},
        provenance_json=envelope.provenance or {},
        raw_hash=current_hash,
        version_no=1,
        is_active=True,
    )
    db.add(new_obs)
    connector.last_synced_at = now
    db.flush()

    return DeduplicationResult(
        is_duplicate=False,
        deduplication_key=dedup_key,
        record_hash=current_hash,
        action_taken="created",
        observation_id=new_obs.id,
    )
