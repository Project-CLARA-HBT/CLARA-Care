"""Scribe session status lifecycle (Requirement 8.1, Property 5).

Pure, dependency-free transition table. The session status moves only along the
declared edges: ``draft -> in_review -> signed -> exported``, plus an
``amended`` branch from ``signed`` (and re-signing an amendment). Any other
transition is illegal and must be rejected by the API.
"""

from __future__ import annotations

__all__ = ["STATUSES", "ALLOWED_TRANSITIONS", "can_transition"]

STATUSES = ("draft", "in_review", "signed", "exported", "amended")

# from_status -> set of legal to_statuses.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"in_review"}),
    "in_review": frozenset({"signed", "draft"}),  # may return to draft to keep editing
    "signed": frozenset({"exported", "amended"}),
    "exported": frozenset(),  # terminal
    "amended": frozenset({"signed"}),  # re-sign the amendment
}


def can_transition(from_status: str, to_status: str) -> bool:
    """Return True iff ``from_status -> to_status`` is a legal lifecycle edge."""

    src = (from_status or "").strip().lower()
    dst = (to_status or "").strip().lower()
    if src not in ALLOWED_TRANSITIONS or dst not in STATUSES:
        return False
    return dst in ALLOWED_TRANSITIONS[src]
