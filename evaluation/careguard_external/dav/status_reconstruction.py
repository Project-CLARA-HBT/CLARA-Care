"""Produce conservative as-of statuses from affirmative official event evidence."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .normalize import write_parquet

EVENT_TYPES = frozenset(
    {"ISSUED", "WITHDRAWN", "RENEWED", "CONTINUED_VALIDITY", "AMENDED", "CORRECTED"}
)


def reconstruct(root: Path, as_of: str, events: list[dict], unresolved: list[dict]) -> list[dict]:
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("invalid_as_of_date") from exc
    unresolved_numbers = {row["registration_number"] for row in unresolved}
    groups: dict[str, list[dict]] = {}
    for event in events:
        number = event.get("registration_number")
        if not isinstance(number, str) or not number:
            raise ValueError("event_missing_registration_number")
        if event.get("event_type") not in EVENT_TYPES:
            raise ValueError("event_unknown_type")
        if not event.get("evidence_document_id"):
            raise ValueError("event_missing_evidence_document_id")
        groups.setdefault(number, []).append(event)
    rows = []
    for number, chain in sorted(groups.items()):
        kinds = {event["event_type"] for event in chain}
        status = (
            "STATUS_UNRESOLVED"
            if number in unresolved_numbers
            else "WITHDRAWN"
            if "WITHDRAWN" in kinds
            else "HISTORICAL"
        )
        rows.append(
            {
                "registration_number": number,
                "status_as_of": as_of,
                "status": status,
                "evidence_document_ids": [event["evidence_document_id"] for event in chain],
            }
        )
    write_parquet(rows, root / "normalized" / f"status_as_of_{as_of}.parquet")
    return rows
