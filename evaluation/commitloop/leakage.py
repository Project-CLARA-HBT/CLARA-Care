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
    scrubbed = json.loads(json.dumps(packet))
    context = scrubbed.get("context")
    # A production commitment snapshot intentionally contains the *input*
    # commitment's OPEN/CLEAR/UNKNOWN state. It is not construction gold: the
    # final lifecycle must still be inferred from its governed source ledger.
    # Permit only this bounded projection, after proving the production origin.
    if isinstance(context, dict) and isinstance(context.get("production_path"), dict):
        provenance = context["production_path"]
        if (
            provenance.get("component") != "api_owned_gst_commitment_thss"
            or provenance.get("gold_derived") is not False
        ):
            raise ValueError("production_context_provenance_invalid")
        commitments = context.get("commitments")
        if not isinstance(commitments, list) or any(
            not isinstance(item, dict)
            or (
                context.get("representation") != "glhs_thss_task_minimal_v1"
                and (
                    item.get("lifecycle_state") != "OPEN"
                    or item.get("evidence_state") != "CLEAR"
                    or item.get("timeliness_state") != "UNKNOWN"
                )
            )
            for item in commitments
        ):
            raise ValueError("production_context_initial_state_invalid")
        for item in commitments:
            if isinstance(item, dict):
                for key in ("lifecycle_state", "evidence_state", "timeliness_state"):
                    item.pop(key, None)
    raw = json.dumps(scrubbed, sort_keys=True)
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
