from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from clara_api.connected_health.schemas import (
    CanonicalHealthRecord,
    ConnectorImportBatch,
    ConnectorRecordTombstone,
)

NOW = datetime(2026, 7, 25, 2, 0, tzinfo=UTC)
RAW_HASH = "sha256:" + ("a" * 64)


def _record(**overrides: object) -> CanonicalHealthRecord:
    payload: dict[str, object] = {
        "profile_id": "prof_1",
        "connector_id": "con_1",
        "provider": "health_connect",
        "provider_record_id": "record-1",
        "record_type": "steps",
        "value": {"scalar": 1200, "unit": "count"},
        "observed_start": NOW - timedelta(hours=1),
        "observed_end": NOW,
        "zone_offset_start": "+07:00",
        "zone_offset_end": "+07:00",
        "data_origin": "com.vendor.health",
        "device": {"manufacturer": "Vendor", "model": "Watch 1", "type": "watch"},
        "recording_method": "automatic",
        "provider_updated_at": NOW,
        "quality": {"state": "source_asserted", "flags": ["AUTO_RECORDED"]},
        "provenance": {"adapter_version": "android-1.0.0", "raw_hash": RAW_HASH},
    }
    payload.update(overrides)
    return CanonicalHealthRecord.model_validate(payload)


def test_accepts_canonical_steps_and_normalizes_quality_flags() -> None:
    record = _record()

    assert record.value.scalar == 1200
    assert record.quality.flags == ["auto_recorded"]
    assert record.schema_version == "1.0"


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"scalar": -1, "unit": "count"}, "non-negative integer"),
        ({"scalar": 1.5, "unit": "count"}, "non-negative integer"),
        ({"scalar": 1, "unit": "steps"}, "non-negative integer"),
    ],
)
def test_rejects_invalid_steps(value: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _record(value=value)


def test_rejects_non_finite_measurement() -> None:
    with pytest.raises(ValidationError, match="finite"):
        _record(value={"scalar": float("nan"), "unit": "count"})


def test_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="time-zone offset"):
        _record(observed_start=datetime(2026, 7, 25, 1, 0))


def test_rejects_reversed_interval() -> None:
    with pytest.raises(ValidationError, match="must not precede"):
        _record(observed_start=NOW, observed_end=NOW - timedelta(seconds=1))


def test_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError):
        _record(schema_version="2.0")


def test_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        _record(secret_debug_payload={"token": "must-not-pass"})


def test_accepts_blood_pressure_components() -> None:
    record = _record(
        record_type="blood_pressure",
        value={"components": {"systolic": 120, "diastolic": 80}, "unit": "mm[Hg]"},
    )

    assert record.value.components == {"systolic": 120, "diastolic": 80}


def test_rejects_blood_pressure_scalar() -> None:
    with pytest.raises(ValidationError, match="systolic/diastolic"):
        _record(record_type="blood_pressure", value={"scalar": 120, "unit": "mm[Hg]"})


def test_import_batch_requires_consistent_scope() -> None:
    with pytest.raises(ValidationError, match="match the batch profile"):
        ConnectorImportBatch(
            idempotency_key="batch_1",
            profile_id="prof_other",
            connector_id="con_1",
            provider="health_connect",
            records=[_record()],
        )


def test_import_batch_accepts_records_and_tombstones() -> None:
    batch = ConnectorImportBatch(
        idempotency_key="batch_1",
        profile_id="prof_1",
        connector_id="con_1",
        provider="health_connect",
        records=[_record()],
        tombstones=[
            ConnectorRecordTombstone(
                provider_record_id="old-record",
                data_origin="com.vendor.health",
                deleted_at=NOW,
            )
        ],
    )

    assert len(batch.records) == 1
    assert len(batch.tombstones) == 1


def test_import_batch_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError, match="records or tombstones"):
        ConnectorImportBatch(
            idempotency_key="batch_1",
            profile_id="prof_1",
            connector_id="con_1",
            provider="health_connect",
        )
