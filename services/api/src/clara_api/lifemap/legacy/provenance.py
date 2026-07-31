"""Aggregate-only reconciliation for facts imported before LifeMap V2.

This module intentionally returns category counts only.  It must never expose
the imported health facts or be used by a live LifeMap decision path.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import LifeMapEventRevision

REPORT_CATEGORIES = ("confirmed", "user_reported", "ambiguous", "invalid")


def legacy_provenance_counts(db: Session) -> dict[str, int]:
    """Return no-PHI, certainty-aware counts for pre-V2 imported revisions."""
    counts: Counter[str] = Counter()
    rows = db.execute(
        select(
            LifeMapEventRevision.truth_state,
            LifeMapEventRevision.provenance_json,
        ).where(LifeMapEventRevision.reason_code == "legacy_import")
    )
    for truth_state, raw_provenance in rows:
        state = str(truth_state)
        provenance = raw_provenance if isinstance(raw_provenance, dict) else {}
        if state in {"invalidated", "entered_in_error"}:
            counts["invalid"] += 1
        elif state in {"user_reported", "reported"}:
            counts["user_reported"] += 1
        elif (
            state == "confirmed"
            and provenance.get("confirmation_certainty") == "verified"
        ):
            counts["confirmed"] += 1
        else:
            counts["ambiguous"] += 1
    return {category: counts[category] for category in REPORT_CATEGORIES}
