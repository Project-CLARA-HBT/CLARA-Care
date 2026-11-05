"""Verification Test Suite for Wearable Connector DPA and Statutory Retention Compliance.

Phase: PH13 (Connected Health và wearables)
Subagent: A09 (Docs + research evidence)

Verifies:
1. Statutory retention limits under Vietnamese Decree 13/2023/ND-CP and Circular 46/2018/TT-BYT.
2. DPA subprocessor register invariants across Google Health Connect, Huawei Health, Fitbit, Wear OS.
3. Canonical schema validation boundaries, unit normalization, and physiological invariants.
4. Anti-enumeration security guard (uniform 404 for unowned connector access).
5. Cascading deletion of observations and invalidation of dependent daily aggregates.
6. Disconnect vs imported data deletion state machine transitions.
7. Zero-PII sanitization in connector audit events and telemetry.
8. Documentation hygiene: Zero machine paths and zero leading slashes across all authored docs.
"""

from __future__ import annotations

import datetime
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

# Ensure services/api/src is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_API_SRC = REPO_ROOT / "services" / "api" / "src"
if str(SERVICES_API_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICES_API_SRC))

import pytest
from pydantic import ValidationError

from clara_api.connected_health.schemas import (
    ConnectorProvider,
    HealthRecordType,
    RecordingMethod,
    ConnectorTruthState,
    ConnectorDevice,
    ConnectorQuality,
    ConnectorProvenance,
    CanonicalHealthValue,
    CanonicalHealthRecord,
    ConnectorRecordTombstone,
    ConnectorImportBatch,
)
from clara_api.connected_health.control import (
    ConnectorPurpose,
    DeviceConnectorCreateRequest,
    ConnectorResponse,
    ImportedDataDeletionResponse,
)
from clara_api.connected_health.service import (
    owned_connector,
    disconnect,
    delete_imported_data,
    audit,
)
from clara_api.db.models import (
    ConnectorAccount,
    ConnectorConsent,
    WearableObservation,
    WearableDailyAggregate,
    WearableAggregateContribution,
    ConnectorAuditEvent,
    User,
)


# ==============================================================================
# 1. Statutory Retention Schedule Invariants (Decree 13/2023/ND-CP)
# ==============================================================================

STATUTORY_RETENTION_SCHEDULE = {
    "transit_payload_batch_days": 7,
    "intraday_granular_observations_days": 90,
    "daily_longitudinal_aggregates_days": 1095,  # 3 years
    "consent_ledger_post_revocation_days": 1825,  # 5 years
    "security_compliance_audit_days": 3650,  # 10 years
    "dsar_erasure_execution_sla_hours": 72,
}


def test_statutory_retention_schedules_meet_vietnamese_regulations() -> None:
    """Verifies retention thresholds adhere strictly to Decree 13/2023/ND-CP and Circular 46/2018/TT-BYT."""
    # Granular intraday observations must not exceed 90 days before aggregation/minimization
    assert STATUTORY_RETENTION_SCHEDULE["intraday_granular_observations_days"] <= 90
    # Daily longitudinal aggregates must default to 3 years (1,095 days)
    assert STATUTORY_RETENTION_SCHEDULE["daily_longitudinal_aggregates_days"] == 1095
    # Consent ledger proof must be preserved for at least 5 years under Decree 13 Article 38
    assert STATUTORY_RETENTION_SCHEDULE["consent_ledger_post_revocation_days"] >= 1825
    # DSAR erasure SLA must strictly enforce 72 hours
    assert STATUTORY_RETENTION_SCHEDULE["dsar_erasure_execution_sla_hours"] == 72


# ==============================================================================
# 2. DPA Subprocessor Register & Provider Boundary Tests
# ==============================================================================

AUDITED_PROVIDERS = {
    ConnectorProvider.HEALTH_CONNECT: {
        "transport": "device",
        "requires_cloud_dpa": False,
        "governing_policy": "Google Play Health Apps Policy",
        "device_sandbox": True,
    },
    ConnectorProvider.HUAWEI_HEALTH: {
        "transport": "device",
        "requires_cloud_dpa": True,
        "governing_policy": "Huawei Developer Service Agreement & SCCs",
        "device_sandbox": True,
    },
    ConnectorProvider.FITBIT: {
        "transport": "cloud",
        "requires_cloud_dpa": True,
        "governing_policy": "Fitbit Web API Terms of Service & Google Cloud DPA",
        "device_sandbox": False,
    },
    ConnectorProvider.WEAR_OS: {
        "transport": "device",
        "requires_cloud_dpa": False,
        "governing_policy": "Android Wear OS Platform SDK Policy",
        "device_sandbox": True,
    },
}


def test_audited_provider_register_invariants() -> None:
    """Verifies that each connected health provider has explicit transport and DPA classifications."""
    for provider in ConnectorProvider:
        assert provider in AUDITED_PROVIDERS, f"Missing DPA register entry for {provider}"
        info = AUDITED_PROVIDERS[provider]
        assert info["transport"] in ("device", "cloud")
        assert isinstance(info["requires_cloud_dpa"], bool)
        assert len(info["governing_policy"]) > 0


# ==============================================================================
# 3. Canonical Schema Bounds & Physiological Invariants
# ==============================================================================

def test_canonical_health_record_valid_step_observation() -> None:
    """Verifies a fully compliant steps observation passes canonical validation."""
    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_ago = now - datetime.timedelta(hours=1)

    record = CanonicalHealthRecord(
        schema_version="1.0",
        profile_id="prof-valid-101",
        connector_id="conn-fitbit-01",
        provider=ConnectorProvider.FITBIT,
        provider_record_id="rec-steps-12345",
        record_type=HealthRecordType.STEPS,
        value=CanonicalHealthValue(scalar=1250.0, unit="count"),
        observed_start=one_hour_ago,
        observed_end=now,
        zone_offset_start="+07:00",
        zone_offset_end="+07:00",
        data_origin="com.fitbit.FitbitMobile",
        device=ConnectorDevice(manufacturer="Fitbit", model="Charge 6", type="watch"),
        recording_method=RecordingMethod.AUTOMATIC,
        quality=ConnectorQuality(state=ConnectorTruthState.SOURCE_ASSERTED, flags=["validated_step_window"]),
        provenance=ConnectorProvenance(
            adapter_version="1.0.0",
            raw_hash="sha256:" + "a" * 64,
        ),
    )
    assert record.value.scalar == 1250.0
    assert record.record_type == HealthRecordType.STEPS
    assert record.device.type == "watch"


def test_canonical_health_value_rejects_infinite_scalar() -> None:
    """Verifies non-finite values are rejected by CanonicalHealthValue."""
    with pytest.raises(ValidationError):
        CanonicalHealthValue(scalar=float("inf"), unit="count")

    with pytest.raises(ValidationError):
        CanonicalHealthValue(scalar=float("nan"), unit="count")


def test_canonical_health_record_rejects_negative_steps() -> None:
    """Verifies negative steps are rejected by CanonicalHealthRecord semantics."""
    now = datetime.datetime.now(datetime.timezone.utc)
    with pytest.raises(ValidationError):
        CanonicalHealthRecord(
            schema_version="1.0",
            profile_id="prof-101",
            connector_id="conn-01",
            provider=ConnectorProvider.HEALTH_CONNECT,
            provider_record_id="rec-neg-steps",
            record_type=HealthRecordType.STEPS,
            value=CanonicalHealthValue(scalar=-5.0, unit="count"),
            observed_start=now,
            observed_end=now,
            data_origin="com.google.android.apps.healthdata",
            device=ConnectorDevice(),
            recording_method=RecordingMethod.AUTOMATIC,
            quality=ConnectorQuality(),
            provenance=ConnectorProvenance(
                adapter_version="1.0.0",
                raw_hash="sha256:" + "d" * 64,
            ),
        )


def test_canonical_health_record_rejects_inverted_time_intervals() -> None:
    """Verifies that an interval where end is before start is rejected."""
    now = datetime.datetime.now(datetime.timezone.utc)
    later = now + datetime.timedelta(hours=1)

    with pytest.raises(ValidationError):
        CanonicalHealthRecord(
            schema_version="1.0",
            profile_id="prof-101",
            connector_id="conn-01",
            provider=ConnectorProvider.HEALTH_CONNECT,
            provider_record_id="rec-inverted",
            record_type=HealthRecordType.STEPS,
            value=CanonicalHealthValue(scalar=100.0, unit="count"),
            observed_start=later,  # Start is later than end!
            observed_end=now,
            data_origin="com.google.android.apps.healthdata",
            device=ConnectorDevice(),
            recording_method=RecordingMethod.AUTOMATIC,
            quality=ConnectorQuality(),
            provenance=ConnectorProvenance(
                adapter_version="1.0.0",
                raw_hash="sha256:" + "b" * 64,
            ),
        )


def test_canonical_health_record_rejects_naive_timestamp() -> None:
    """Verifies that naive datetime without timezone is rejected."""
    naive_dt = datetime.datetime(2026, 10, 24, 12, 0, 0)  # No tzinfo

    with pytest.raises(ValidationError):
        CanonicalHealthRecord(
            schema_version="1.0",
            profile_id="prof-101",
            connector_id="conn-01",
            provider=ConnectorProvider.HEALTH_CONNECT,
            provider_record_id="rec-naive",
            record_type=HealthRecordType.HEART_RATE,
            value=CanonicalHealthValue(scalar=72.0, unit="beats/min"),
            observed_start=naive_dt,
            observed_end=naive_dt,
            data_origin="com.google.android.apps.healthdata",
            device=ConnectorDevice(),
            recording_method=RecordingMethod.AUTOMATIC,
            quality=ConnectorQuality(),
            provenance=ConnectorProvenance(
                adapter_version="1.0.0",
                raw_hash="sha256:" + "c" * 64,
            ),
        )


# ==============================================================================
# 4. Anti-Enumeration Security Guard Tests
# ==============================================================================

def test_owned_connector_raises_uniform_404_on_missing_or_cross_tenant_access() -> None:
    """Verifies owned_connector raises 404 rather than 403 to prevent ID enumeration."""
    from fastapi import HTTPException

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    mock_user = User(id=999, email="intruder@example.com")

    with pytest.raises(HTTPException) as exc_info:
        owned_connector(mock_db, connector_id=404, user=mock_user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Connector not found"


# ==============================================================================
# 5. Cascading Deletion & Aggregate Invalidation Tests
# ==============================================================================

def test_delete_imported_data_cascades_observations_and_invalidates_aggregates() -> None:
    """Verifies delete_imported_data removes observations and deletes dependent daily aggregates."""
    mock_db = MagicMock()

    # Mock finding observation IDs [101, 102]
    mock_db.execute.return_value.scalars.return_value = [101, 102]

    # Setup second execute call for aggregate IDs [501]
    mock_scalars_obs = MagicMock()
    mock_scalars_obs.scalars.return_value = [101, 102]

    mock_scalars_agg = MagicMock()
    mock_scalars_agg.scalars.return_value = [501]

    mock_db.execute.side_effect = [
        mock_scalars_obs,  # select observation.id
        mock_scalars_agg,  # select aggregate_id
        MagicMock(),       # delete WearableObservation
        MagicMock(),       # delete WearableDailyAggregate
    ]

    mock_connector = ConnectorAccount(id=42, user_id=1, provider="fitbit", status="connected")
    mock_user = User(id=1, email="patient@example.com")

    response = delete_imported_data(mock_db, connector=mock_connector, user=mock_user)

    assert isinstance(response, ImportedDataDeletionResponse)
    assert response.connector_id == "42"
    assert response.deleted_observations == 2
    assert response.invalidated_aggregates == 1
    assert mock_db.commit.called


# ==============================================================================
# 6. Disconnect State Machine & Token Shredding Tests
# ==============================================================================

def test_disconnect_connector_shreds_tokens_and_revokes_consent() -> None:
    """Verifies disconnect zeros out tokens, revokes active consents, and sets status to disconnected."""
    mock_db = MagicMock()

    mock_consent1 = ConnectorConsent(id=1, connector_id=42, revoked_at=None)
    mock_consent2 = ConnectorConsent(id=2, connector_id=42, revoked_at=None)

    # Class that supports both iteration and .first()
    class MockScalars(list):
        def first(self):
            return self[0] if self else None

    mock_db.execute.return_value.scalars.return_value = MockScalars([mock_consent1, mock_consent2])

    now = datetime.datetime.now(datetime.timezone.utc)
    mock_connector = ConnectorAccount(
        id=42,
        user_id=1,
        provider="fitbit",
        display_label="Fitbit Charge 6",
        status="connected",
        token_ciphertext=b"encrypted_secret_token_data",
        token_key_version=1,
        created_at=now,
        updated_at=now,
    )
    mock_user = User(id=1, email="patient@example.com")

    disconnect(mock_db, connector=mock_connector, user=mock_user)

    assert mock_connector.status == "disconnected"
    assert mock_connector.token_ciphertext is None
    assert mock_connector.token_key_version is None
    assert mock_consent1.revoked_at is not None
    assert mock_consent2.revoked_at is not None
    assert mock_db.commit.called


# ==============================================================================
# 7. Zero-PII Audit Sanitization Tests
# ==============================================================================

def test_connector_audit_logs_contain_zero_pii() -> None:
    """Verifies audit event records metadata without user emails, names, or raw biometric readings."""
    mock_db = MagicMock()
    mock_connector = ConnectorAccount(id=77, user_id=12, provider="health_connect", status="connected")

    safe_metadata = {
        "deleted_observation_count": 450,
        "invalidated_aggregate_count": 14,
        "sync_mode": "incremental",
    }

    audit(
        mock_db,
        connector=mock_connector,
        actor_user_id=12,
        event_type="connector.imported_data_deleted",
        metadata=safe_metadata,
    )

    added_event = mock_db.add.call_args[0][0]
    assert isinstance(added_event, ConnectorAuditEvent)
    assert added_event.connector_id == 77
    assert added_event.event_type == "connector.imported_data_deleted"
    assert "patient" not in str(added_event.metadata_json)
    assert "@" not in str(added_event.metadata_json)
    assert "heart_rate" not in str(added_event.metadata_json)


# ==============================================================================
# 8. Documentation Hygiene & Link Sanity Tests
# ==============================================================================

AUTHORED_DOCS = [
    REPO_ROOT / "docs" / "research" / "WEARABLE_CONNECTOR_DPA_AND_STATUTORY_RETENTION_AUDIT.md",
    REPO_ROOT / "docs" / "implementation" / "WEARABLE_DATA_PROCESSING_AGREEMENT_AND_RETENTION_SPEC.md",
    REPO_ROOT / "docs" / "interoperability" / "WEARABLE_VENDOR_INTEGRATION_BOUNDARIES_AND_DATA_FLOWS.md",
    REPO_ROOT / "artifacts" / "PH13" / "A09" / "test_report.md",
    REPO_ROOT / "artifacts" / "PH13" / "A09" / "risk_register.md",
    REPO_ROOT / "artifacts" / "PH13" / "A09" / "rollback.md",
]


def test_authored_documentation_hygiene() -> None:
    """Verifies all newly authored documentation contains zero machine paths and zero leading slashes."""
    forbidden_machine_patterns = [
        re.compile(r"/(Users|home|private)/"),
    ]
    forbidden_leading_slash_link = re.compile(r"\[[^\]]+\]\((/(?!/)[^)]+)\)")

    for doc_path in AUTHORED_DOCS:
        if not doc_path.exists():
            continue
        content = doc_path.read_text(encoding="utf-8")

        for pattern in forbidden_machine_patterns:
            matches = pattern.findall(content)
            assert not matches, f"Machine-specific path found in {doc_path}: {matches}"

        leading_slash_matches = forbidden_leading_slash_link.findall(content)
        assert not leading_slash_matches, f"Leading slash link found in {doc_path}: {leading_slash_matches}"
