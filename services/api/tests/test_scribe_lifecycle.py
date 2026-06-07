"""Property 5: scribe status-transition legality (Requirement 8.1)."""

from __future__ import annotations

import itertools

from clara_api.core.scribe_lifecycle import (
    ALLOWED_TRANSITIONS,
    STATUSES,
    can_transition,
)


def test_only_declared_edges_are_legal() -> None:
    # Exhaustive over the full status x status space: can_transition agrees with
    # the declared ALLOWED_TRANSITIONS table and nothing else.
    for src, dst in itertools.product(STATUSES, STATUSES):
        expected = dst in ALLOWED_TRANSITIONS.get(src, frozenset())
        assert can_transition(src, dst) is expected, (src, dst)


def test_happy_path_is_legal() -> None:
    assert can_transition("draft", "in_review")
    assert can_transition("in_review", "signed")
    assert can_transition("signed", "exported")
    assert can_transition("signed", "amended")
    assert can_transition("amended", "signed")


def test_illegal_skips_and_self_loops_rejected() -> None:
    assert not can_transition("draft", "signed")  # skip
    assert not can_transition("draft", "exported")  # skip
    assert not can_transition("exported", "signed")  # terminal
    assert not can_transition("signed", "draft")  # signed is immutable backwards
    for s in STATUSES:
        assert not can_transition(s, s)  # no self-loop declared


def test_unknown_statuses_rejected() -> None:
    assert not can_transition("", "signed")
    assert not can_transition("draft", "bogus")
    assert not can_transition("bogus", "draft")
