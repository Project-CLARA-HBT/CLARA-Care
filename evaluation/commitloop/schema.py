from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TimelineEvent:
    evidence_id: str
    resource_type: str
    resource_id: str
    subject_token: str
    status: str | None
    codes: tuple[tuple[str, str], ...]
    valid_at: datetime | None
    known_at: datetime
    encounter_reference: str | None
    source: dict[str, Any]


@dataclass(frozen=True)
class ConstructedCase:
    case_id: str
    subject_token: str
    status: str
    reason: str | None
    anchor_evidence_id: str | None
    domain: str | None
    action: str | None
    target: dict[str, str] | None
    anchor_valid_time: datetime | None
    anchor_known_time: datetime | None
    due_time: datetime | None
    fulfillment_predicate: dict[str, Any] | None
