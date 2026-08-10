"""Fail-closed checks that solver packets cannot see construction truth or future evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

FORBIDDEN_SOLVER_KEYS = frozenset(
    {
        "construction_gold",
        "gold_label",
        "lifecycle_state",
        "evidence_state",
        "timeliness_state",
        "escalation_state",
    }
)


def validate_solver_packet(packet: dict[str, Any], *, known_cutoff: datetime) -> None:
    raw = json.dumps(packet, sort_keys=True)
    lowered = raw.lower()
    if any(f'"{key}"' in lowered for key in FORBIDDEN_SOLVER_KEYS):
        raise ValueError("solver_packet_contains_gold")
    context = packet.get("context")
    events = context.get("events", []) if isinstance(context, dict) else []
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("invalid_solver_event")
        known_at = event.get("known_at")
        if isinstance(known_at, str) and datetime.fromisoformat(known_at) > known_cutoff:
            raise ValueError("solver_packet_future_knowledge_leakage")
