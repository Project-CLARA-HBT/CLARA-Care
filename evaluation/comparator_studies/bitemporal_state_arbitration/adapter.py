"""Exact adapter from frozen CommitLoop event packets to the BTSA mechanism."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from evaluation.comparator_studies.bitemporal_state_arbitration.engine import (
    ArbitrationEvent,
    arbitrate,
)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("btsa_timestamp_required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("btsa_timezone_required")
    return parsed.astimezone(UTC)


def btsa_context(
    events: list[dict[str, Any]], *, valid_at: datetime, known_at: datetime
) -> dict[str, Any]:
    """Run the documented mechanism without adding GLHS governance semantics."""

    arbitration_events = []
    source_by_id: dict[str, dict[str, Any]] = {}
    excluded = []
    for item in events:
        event_id = item.get("evidence_id")
        if not isinstance(event_id, str) or not event_id or event_id in source_by_id:
            raise ValueError("btsa_event_id_invalid")
        source_by_id[event_id] = item
        if item.get("valid_at") is None:
            excluded.append({"evidence_id": event_id, "reason": "VALID_TIME_MISSING"})
            continue
        raw_codes = item.get("codes", [])
        codes = tuple(
            (str(pair[0]), str(pair[1]))
            for pair in raw_codes
            if isinstance(pair, list) and len(pair) == 2
        )
        slot = json.dumps(
            [str(item.get("resource_type", "")), codes],
            sort_keys=True,
            separators=(",", ":"),
        )
        status = item.get("status")
        relation = item.get("btsa_relation", "SUPPORT")
        target_id = item.get("btsa_target_id")
        if not isinstance(status, str) or not status:
            excluded.append({"evidence_id": event_id, "reason": "VALUE_MISSING"})
            continue
        if (
            not isinstance(relation, str)
            or target_id is not None
            and not isinstance(target_id, str)
        ):
            raise ValueError("btsa_relation_invalid")
        arbitration_events.append(
            ArbitrationEvent(
                event_id=event_id,
                slot=slot,
                value=status,
                valid_from=_timestamp(item["valid_at"]),
                valid_to=None,
                known_at=_timestamp(item["known_at"]),
                authority=0,
                relation=relation,
                target_id=target_id,
            )
        )
    result = arbitrate(arbitration_events, valid_at=valid_at, known_at=known_at)
    return {
        "representation": "bitemporal_state_arbitration_mechanism_v1",
        "events": [source_by_id[event_id] for event_id in result.active_ids],
        "active_evidence_ids": list(result.active_ids),
        "superseded_evidence_ids": list(result.superseded_ids),
        "conflict_evidence_ids": list(result.conflict_ids),
        "historical_evidence_ids": list(result.historical_ids),
        "excluded": excluded,
        "authority_mode": "uniform_unranked",
        "governance_status": "UNSUPPORTED_BY_METHOD",
        "fidelity_status": "MECHANISM_MAPPED_NOT_END_TO_END_REPRODUCTION",
    }
