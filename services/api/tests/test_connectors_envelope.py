"""Unit tests for ConnectedObservationEnvelope and deduplication engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.connectors.envelope import (
    ConnectedObservationEnvelope,
    EnvelopeDeduplicator,
    ingest_observation_envelope,
)
from clara_api.db.models import (
    ConnectorAccount,
    PhrProfile,
    User,
    WearableObservation,
    WearableObservationVersion,
)
from clara_api.db.session import SessionLocal

# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------


def _create_user_and_profile(db: Session) -> tuple[User, PhrProfile]:
    suffix = uuid4().hex[:8]
    user = User(
        email=f"connector-test-{suffix}@clara.vn",
        hashed_password="test-password-hash",
        role="normal",
        is_email_verified=True,
        status="active",
    )
    db.add(user)
    db.flush()

    profile = PhrProfile(
        user_id=user.id,
        full_name="Nguyễn Văn Connect",
        gender="male",
        status="active",
        current_version_no=1,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    db.refresh(profile)
    return user, profile


# ---------------------------------------------------------------------------
# Schema Validation Tests
# ---------------------------------------------------------------------------


def test_connected_observation_envelope_valid() -> None:
    now = datetime.now(UTC)
    envelope = ConnectedObservationEnvelope(
        profile_id=1,
        source_system="health_connect",
        source_record_id="rec_step_101",
        source_device_id="pixel_watch_3",
        data_type="steps",
        effective_start=now - timedelta(minutes=30),
        effective_end=now,
        observed_value={"count": 2450},
        unit="count",
        source_version="v1.2",
        provenance={"package": "com.google.android.apps.healthdata"},
    )

    assert envelope.profile_id == 1
    assert envelope.source_system == "health_connect"
    assert envelope.source_record_id == "rec_step_101"
    assert envelope.source_device_id == "pixel_watch_3"
    assert envelope.data_type == "steps"
    assert envelope.observed_value == {"count": 2450}
    assert envelope.unit == "count"
    assert envelope.source_version == "v1.2"
    assert envelope.deduplication_key == "1:health_connect:rec_step_101:v1.2"
    assert envelope.payload_hash.startswith("sha256:")


@pytest.mark.parametrize(
    "source_system",
    ["health_connect", "apple_health", "dexcom", "fitbit"],
)
def test_supported_source_systems(source_system: str) -> None:
    now = datetime.now(UTC)
    envelope = ConnectedObservationEnvelope(
        profile_id=1,
        source_system=source_system,
        source_record_id="rec_001",
        data_type="heart_rate",
        effective_start=now,
        observed_value={"bpm": 75},
    )
    assert envelope.source_system == source_system


def test_invalid_source_system_rejected() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError) as exc_info:
        ConnectedObservationEnvelope(
            profile_id=1,
            source_system="unsupported_tracker",
            source_record_id="rec_001",
            data_type="heart_rate",
            effective_start=now,
            observed_value={"bpm": 75},
        )
    assert "Invalid source_system" in str(exc_info.value)


@pytest.mark.parametrize(
    "data_type",
    [
        "steps",
        "sleep",
        "heart_rate",
        "blood_pressure",
        "oxygen_saturation",
        "body_weight",
        "blood_glucose",
    ],
)
def test_supported_data_types(data_type: str) -> None:
    now = datetime.now(UTC)
    envelope = ConnectedObservationEnvelope(
        profile_id=1,
        source_system="apple_health",
        source_record_id="rec_002",
        data_type=data_type,
        effective_start=now,
        observed_value={"val": 100},
    )
    assert envelope.data_type == data_type


def test_invalid_data_type_rejected() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError) as exc_info:
        ConnectedObservationEnvelope(
            profile_id=1,
            source_system="apple_health",
            source_record_id="rec_002",
            data_type="unknown_metric",
            effective_start=now,
            observed_value={"val": 100},
        )
    assert "Invalid data_type" in str(exc_info.value)


def test_invalid_interval_rejected() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError) as exc_info:
        ConnectedObservationEnvelope(
            profile_id=1,
            source_system="apple_health",
            source_record_id="rec_003",
            data_type="steps",
            effective_start=now,
            effective_end=now - timedelta(minutes=10),  # End precedes start!
            observed_value={"count": 100},
        )
    assert "effective_end cannot precede effective_start" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Deduplication Logic Tests
# ---------------------------------------------------------------------------


def test_in_memory_envelope_deduplicator() -> None:
    now = datetime.now(UTC)
    envelope = ConnectedObservationEnvelope(
        profile_id=1,
        source_system="dexcom",
        source_record_id="cgm_reading_888",
        data_type="blood_glucose",
        effective_start=now,
        observed_value={"mg_dl": 115},
        unit="mg/dL",
        source_version="rev1",
    )

    deduplicator = EnvelopeDeduplicator()

    # First attempt: not a duplicate
    assert deduplicator.is_duplicate(envelope) is False

    # Immediate retry: duplicate detected!
    assert deduplicator.is_duplicate(envelope) is True

    # Same record but updated value / payload: not a duplicate
    modified_envelope = ConnectedObservationEnvelope(
        profile_id=1,
        source_system="dexcom",
        source_record_id="cgm_reading_888",
        data_type="blood_glucose",
        effective_start=now,
        observed_value={"mg_dl": 120},  # Value changed
        unit="mg/dL",
        source_version="rev1",
    )
    assert deduplicator.is_duplicate(modified_envelope) is False


def test_database_deduplication_and_ingestion() -> None:
    db = SessionLocal()
    try:
        user, profile = _create_user_and_profile(db)
        now = datetime.now(UTC)

        envelope = ConnectedObservationEnvelope(
            profile_id=profile.id,
            source_system="fitbit",
            source_record_id="fitbit_hr_123",
            source_device_id="charge_6",
            data_type="heart_rate",
            effective_start=now - timedelta(minutes=5),
            effective_end=now,
            observed_value={"bpm": 68},
            unit="beats/min",
            source_version="1.0",
        )

        # 1. First Ingestion -> Creates new observation
        result1 = ingest_observation_envelope(db, envelope, user=user)
        db.commit()

        assert result1.is_duplicate is False
        assert result1.action_taken == "created"
        assert result1.observation_id is not None

        # Verify ConnectorAccount was auto-provisioned
        connector = db.execute(
            select(ConnectorAccount).where(
                ConnectorAccount.profile_id == profile.id,
                ConnectorAccount.provider == "fitbit",
            )
        ).scalars().first()
        assert connector is not None
        assert connector.status == "connected"
        assert connector.last_synced_at is not None

        # Verify WearableObservation exists
        obs_count = db.execute(
            select(func.count(WearableObservation.id)).where(
                WearableObservation.connector_id == connector.id,
                WearableObservation.provider_record_id == "fitbit_hr_123",
            )
        ).scalar()
        assert obs_count == 1

        # 2. Retry identical Envelope -> Deduplicated NOOP
        result2 = ingest_observation_envelope(db, envelope, user=user)
        db.commit()

        assert result2.is_duplicate is True
        assert result2.action_taken == "deduplicated_noop"
        assert result2.observation_id == result1.observation_id

        # Verify no duplicate rows were created in DB
        obs_count_retry = db.execute(
            select(func.count(WearableObservation.id)).where(
                WearableObservation.connector_id == connector.id,
                WearableObservation.provider_record_id == "fitbit_hr_123",
            )
        ).scalar()
        assert obs_count_retry == 1

        # 3. Ingestion with modified value / new revision -> Updates and creates version snapshot
        updated_envelope = ConnectedObservationEnvelope(
            profile_id=profile.id,
            source_system="fitbit",
            source_record_id="fitbit_hr_123",
            source_device_id="charge_6",
            data_type="heart_rate",
            effective_start=now - timedelta(minutes=5),
            effective_end=now,
            observed_value={"bpm": 74},  # Calibrated value
            unit="beats/min",
            source_version="1.1",
        )

        result3 = ingest_observation_envelope(db, updated_envelope, user=user)
        db.commit()

        assert result3.is_duplicate is False
        assert result3.action_taken == "updated"
        assert result3.observation_id == result1.observation_id

        # Verify version snapshot was archived
        versions = list(
            db.execute(
                select(WearableObservationVersion).where(
                    WearableObservationVersion.observation_id == result1.observation_id
                )
            ).scalars()
        )
        assert len(versions) == 1
        assert versions[0].version_no == 1
        assert versions[0].snapshot_json["value"] == {"bpm": 68}

        # Verify active observation has new value and version 2
        updated_obs = db.get(WearableObservation, result1.observation_id)
        assert updated_obs is not None
        assert updated_obs.version_no == 2
        assert updated_obs.value_json == {"bpm": 74}

    finally:
        db.close()
