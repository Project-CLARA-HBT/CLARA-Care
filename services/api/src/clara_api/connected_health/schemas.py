"""Versioned canonical contracts for health and wearable connectors."""

from __future__ import annotations

import math
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
_ZONE_OFFSET_PATTERN = re.compile(r"^(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$")


class ConnectorProvider(StrEnum):
    HEALTH_CONNECT = "health_connect"
    HUAWEI_HEALTH = "huawei_health"
    FITBIT = "fitbit"
    WEAR_OS = "wear_os"


class HealthRecordType(StrEnum):
    STEPS = "steps"
    ACTIVITY = "activity"
    HEART_RATE = "heart_rate"
    RESTING_HEART_RATE = "resting_heart_rate"
    SLEEP = "sleep"
    WEIGHT = "weight"
    BODY_FAT = "body_fat"
    BLOOD_PRESSURE = "blood_pressure"
    BLOOD_GLUCOSE = "blood_glucose"
    OXYGEN_SATURATION = "oxygen_saturation"
    BODY_TEMPERATURE = "body_temperature"


class RecordingMethod(StrEnum):
    AUTOMATIC = "automatic"
    ACTIVE = "active"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class ConnectorTruthState(StrEnum):
    SOURCE_ASSERTED = "source_asserted"
    USER_CONFIRMED = "user_confirmed"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class ConnectorDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = Field(default="", max_length=128)
    model: str = Field(default="", max_length=128)
    type: str = Field(default="unknown", max_length=64)


class ConnectorQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ConnectorTruthState = ConnectorTruthState.SOURCE_ASSERTED
    flags: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("flags")
    @classmethod
    def normalize_flags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for flag in value:
            clean = flag.strip().lower()
            if not clean or len(clean) > 64:
                raise ValueError("quality flags must contain 1-64 characters")
            if clean not in normalized:
                normalized.append(clean)
        return normalized


class ConnectorProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_version: str = Field(min_length=1, max_length=64)
    raw_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class CanonicalHealthValue(BaseModel):
    """A scalar or named component measurement in its original declared unit."""

    model_config = ConfigDict(extra="forbid")

    scalar: float | None = None
    components: dict[str, float] | None = None
    unit: str = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_shape_and_finiteness(self) -> CanonicalHealthValue:
        has_scalar = self.scalar is not None
        has_components = self.components is not None
        if has_scalar == has_components:
            raise ValueError("value must contain exactly one of scalar or components")
        numbers = [self.scalar] if has_scalar else list((self.components or {}).values())
        if not numbers or any(number is None or not math.isfinite(number) for number in numbers):
            raise ValueError("measurement values must be finite")
        if self.components is not None:
            if len(self.components) > 16:
                raise ValueError("measurement has too many components")
            for key in self.components:
                if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", key):
                    raise ValueError("component keys must use lower snake_case")
        return self


class CanonicalHealthRecord(BaseModel):
    """Provider-neutral record with sufficient provenance for safe replay."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    connector_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    provider: ConnectorProvider
    provider_record_id: str = Field(min_length=1, max_length=512)
    record_type: HealthRecordType
    value: CanonicalHealthValue
    observed_start: datetime
    observed_end: datetime
    zone_offset_start: str | None = Field(default=None, max_length=6)
    zone_offset_end: str | None = Field(default=None, max_length=6)
    data_origin: str = Field(min_length=1, max_length=255)
    device: ConnectorDevice = Field(default_factory=ConnectorDevice)
    recording_method: RecordingMethod = RecordingMethod.UNKNOWN
    provider_updated_at: datetime | None = None
    ingested_at: datetime | None = None
    quality: ConnectorQuality = Field(default_factory=ConnectorQuality)
    provenance: ConnectorProvenance

    @field_validator(
        "observed_start",
        "observed_end",
        "provider_updated_at",
        "ingested_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must include a time-zone offset")
        return value

    @field_validator("zone_offset_start", "zone_offset_end")
    @classmethod
    def validate_zone_offset(cls, value: str | None) -> str | None:
        if value is not None and not _ZONE_OFFSET_PATTERN.fullmatch(value):
            raise ValueError("zone offset must be Z or ±HH:MM")
        return value

    @model_validator(mode="after")
    def validate_record_semantics(self) -> CanonicalHealthRecord:
        if self.observed_end < self.observed_start:
            raise ValueError("observed_end must not precede observed_start")

        scalar = self.value.scalar
        components = self.value.components or {}
        unit = self.value.unit

        if self.record_type is HealthRecordType.STEPS:
            if scalar is None or scalar < 0 or not scalar.is_integer() or unit != "count":
                raise ValueError("steps require a non-negative integer scalar in count")
        elif self.record_type in {
            HealthRecordType.HEART_RATE,
            HealthRecordType.RESTING_HEART_RATE,
        }:
            if scalar is None or not 0 <= scalar <= 300 or unit != "beats/min":
                raise ValueError("heart rate requires a scalar from 0-300 beats/min")
        elif self.record_type is HealthRecordType.WEIGHT:
            if scalar is None or not 0 < scalar <= 1000 or unit != "kg":
                raise ValueError("weight requires a positive scalar up to 1000 kg")
        elif self.record_type is HealthRecordType.BODY_FAT:
            if scalar is None or not 0 <= scalar <= 100 or unit != "%":
                raise ValueError("body fat requires a scalar from 0-100 %")
        elif self.record_type is HealthRecordType.OXYGEN_SATURATION:
            if scalar is None or not 0 <= scalar <= 100 or unit != "%":
                raise ValueError("oxygen saturation requires a scalar from 0-100 %")
        elif self.record_type is HealthRecordType.BLOOD_PRESSURE:
            if set(components) != {"systolic", "diastolic"} or unit != "mm[Hg]":
                raise ValueError("blood pressure requires systolic/diastolic in mm[Hg]")
            if any(not 0 < component <= 400 for component in components.values()):
                raise ValueError("blood pressure components must be within 0-400 mm[Hg]")
        return self


class ConnectorRecordTombstone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_record_id: str = Field(min_length=1, max_length=512)
    data_origin: str = Field(min_length=1, max_length=255)
    deleted_at: datetime

    @field_validator("deleted_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deleted_at must include a time-zone offset")
        return value


class ConnectorImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    idempotency_key: str = Field(pattern=_IDENTIFIER_PATTERN)
    profile_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    connector_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    provider: ConnectorProvider
    cursor: str | None = Field(default=None, max_length=2048)
    records: list[CanonicalHealthRecord] = Field(default_factory=list, max_length=500)
    tombstones: list[ConnectorRecordTombstone] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_batch_scope(self) -> ConnectorImportBatch:
        if not self.records and not self.tombstones:
            raise ValueError("import batch must include records or tombstones")
        for record in self.records:
            if (
                record.profile_id != self.profile_id
                or record.connector_id != self.connector_id
                or record.provider is not self.provider
            ):
                raise ValueError(
                    "every record must match the batch profile, connector, and provider"
                )
        return self
