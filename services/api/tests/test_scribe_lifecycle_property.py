"""Property 5: scribe status-transition legality (Requirement 8.1) — Hypothesis.

``test_scribe_lifecycle.py`` pins this exhaustively over the known status set.
This module strengthens it with randomized Hypothesis strategies that also throw
*arbitrary* strings (garbage, casing, whitespace) at ``can_transition`` to assert
it permits ONLY the declared lifecycle edges and rejects everything else.

Validates: Requirements 8.1
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_api.core.scribe_lifecycle import (
    ALLOWED_TRANSITIONS,
    STATUSES,
    can_transition,
)

# A mix of real statuses (incl. odd casing / surrounding whitespace, which the
# function normalizes) and pure-garbage tokens that must always be rejected.
_known_status = st.sampled_from(STATUSES)
_decorated_status = _known_status.flatmap(
    lambda s: st.sampled_from([s, s.upper(), s.title(), f"  {s} ", f"{s}\t"])
)
_garbage = st.text(max_size=12).filter(lambda s: s.strip().lower() not in STATUSES)
_status = st.one_of(_known_status, _decorated_status, _garbage)


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


# Feature: clara-scribe-enterprise, Property 5: Transition legality
# Validates: Requirements 8.1
@settings(max_examples=400, deadline=None)
@given(src=_status, dst=_status)
def test_p5_can_transition_matches_declared_table_only(src: str, dst: str) -> None:
    nsrc, ndst = _normalize(src), _normalize(dst)
    # The single source of truth: legal iff the normalized edge is declared AND
    # the destination is a real status.
    expected = ndst in STATUSES and ndst in ALLOWED_TRANSITIONS.get(nsrc, frozenset())
    assert can_transition(src, dst) is expected, (src, dst)


# Feature: clara-scribe-enterprise, Property 5: no transition outside the graph
# Validates: Requirements 8.1
@settings(max_examples=200, deadline=None)
@given(src=_status, dst=_garbage)
def test_p5_unknown_destination_always_rejected(src: str, dst: str) -> None:
    # Any destination that is not a declared status can never be reached.
    assert can_transition(src, dst) is False


# Feature: clara-scribe-enterprise, Property 5: no self-loops / terminal stays terminal
# Validates: Requirements 8.1
@settings(max_examples=100, deadline=None)
@given(status=_known_status)
def test_p5_no_self_loops_and_terminal_is_sink(status: str) -> None:
    # No status declares an edge to itself.
    assert can_transition(status, status) is False
    # 'exported' is terminal: it has no outgoing legal edge to any status.
    if status == "exported":
        assert all(not can_transition("exported", dst) for dst in STATUSES)
