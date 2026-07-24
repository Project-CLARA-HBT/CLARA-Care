"""Public control-plane contracts for connected health sources."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from clara_api.connected_health.schemas import ConnectorProvider, HealthRecordType

ConnectorPurpose = Literal[
    "personal_health_assistance",
    "lifemap_context",
    "research",
]


class DeviceConnectorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal[
        ConnectorProvider.HEALTH_CONNECT,
        ConnectorProvider.HUAWEI_HEALTH,
        ConnectorProvider.WEAR_OS,
    ]
    external_subject_ref: str = Field(min_length=1, max_length=255)
    display_label: str = Field(default="", max_length=255)
    consent_version: Literal["1.0"] = "1.0"
    purposes: list[ConnectorPurpose] = Field(min_length=1, max_length=3)
    data_types: list[HealthRecordType] = Field(min_length=1, max_length=16)

    @field_validator("purposes", "data_types")
    @classmethod
    def unique_values(cls, value: list) -> list:
        if len(value) != len(set(value)):
            raise ValueError("values must not contain duplicates")
        return value


class ConnectorCapabilityResponse(BaseModel):
    provider: ConnectorProvider
    transport: Literal["device", "cloud"]
    client_detection_required: bool
    supported_data_types: list[HealthRecordType]
    limitations: list[str] = Field(default_factory=list)


class ConnectorResponse(BaseModel):
    id: str
    provider: ConnectorProvider
    display_label: str
    status: str
    data_types: list[HealthRecordType]
    purposes: list[ConnectorPurpose]
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectorOperationResponse(BaseModel):
    connector: ConnectorResponse
    action: Literal[
        "none",
        "device_import_required",
        "reauthorization_required",
    ] = "none"


class ImportedDataDeletionResponse(BaseModel):
    connector_id: str
    deleted_observations: int
    invalidated_aggregates: int


class ConnectorImportResponse(BaseModel):
    batch_id: str
    idempotent_replay: bool = False
    accepted_count: int
    rejected_count: int
    upserted_count: int
    tombstoned_count: int
