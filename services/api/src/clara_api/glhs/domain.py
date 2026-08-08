"""Closed GLHS vocabulary and pure validation helpers.

The vocabulary is deliberately small and code-owned.  Free-text or model
supplied status strings cannot silently become a state transition policy.
"""

from __future__ import annotations

from datetime import datetime

POLICY_VERSION = "glhs.v1"
EPISTEMIC_STATES = frozenset(
    {"reported", "extracted", "documented", "inferred", "confirmed", "disputed", "unknown"}
)
LIFECYCLE_STATES = frozenset(
    {"candidate", "active", "superseded", "resolved", "rejected", "entered_in_error"}
)
ACTIVE_LIFECYCLE_STATES = frozenset({"active"})
FINAL_LIFECYCLE_STATES = frozenset({"superseded", "resolved", "rejected", "entered_in_error"})
EVIDENCE_RELATIONS = frozenset({"supports", "contradicts", "context"})
RELATION_TYPES = frozenset({"duplicates", "supersedes", "contradicts", "related_to"})
TRANSITION_ACTIONS = frozenset({"activate", "supersede", "reject", "resolve", "enter_in_error"})
TIME_PRECISIONS = frozenset({"exact", "day", "month", "year", "estimated", "unknown"})


class GlhsInvariantError(ValueError):
    """Raised before a canonical GLHS write could violate an invariant."""


def require_member(value: str, allowed: frozenset[str], *, field: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in allowed:
        raise GlhsInvariantError(f"invalid_{field}")
    return normalized


def validate_time_window(valid_from: datetime, valid_to: datetime | None) -> None:
    if valid_to is not None and valid_to < valid_from:
        raise GlhsInvariantError("invalid_valid_time_window")


def intervals_overlap(
    left_from: datetime,
    left_to: datetime | None,
    right_from: datetime,
    right_to: datetime | None,
) -> bool:
    """Inclusive interval overlap; a missing end is an open interval."""

    if left_to is not None and left_to < right_from:
        return False
    if right_to is not None and right_to < left_from:
        return False
    return True
