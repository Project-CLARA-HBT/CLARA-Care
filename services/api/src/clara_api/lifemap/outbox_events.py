"""Versioned, minimum-data LifeMap integration-event contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventKind = Literal[
    "fact",
    "episode",
    "task",
    "consent",
    "correction",
    "invalidation",
    "other",
]


class LifeMapIntegrationEvent(BaseModel):
    """No-clinical-text envelope delivered by the transactional outbox."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["lifemap.outbox.v1"] = "lifemap.outbox.v1"
    event_id: str = Field(min_length=1, max_length=64)
    profile_id: str = Field(min_length=1, max_length=36)
    aggregate_type: str = Field(min_length=1, max_length=64)
    aggregate_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(
        min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_.-]+$"
    )
    event_kind: EventKind
    occurred_at: datetime


def event_kind(event_type: str) -> EventKind:
    if event_type in {
        "lifemap.event.corrected",
        "lifemap.event.superseded",
    }:
        return "correction"
    if event_type in {
        "lifemap.event.invalidated",
        "lifemap.event.entered_in_error",
    }:
        return "invalidation"
    if event_type.startswith("lifemap.event."):
        return "fact"
    if event_type.startswith("lifemap.episode."):
        return "episode"
    if event_type.startswith("lifemap.task."):
        return "task"
    if event_type.startswith("lifemap.consent."):
        return "consent"
    return "other"
