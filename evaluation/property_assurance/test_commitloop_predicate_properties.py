"""Property assurance for the bounded CommitLoop predicate interpreter."""

from __future__ import annotations

from clara_api.glhs.predicate_dsl import evaluate_predicate
from hypothesis import given
from hypothesis import strategies as st


@st.composite
def _events(draw):
    identifiers = draw(st.lists(st.sampled_from(["a", "b", "c"]), min_size=0, max_size=12))
    return [
        {
            "evidence_id": identifier,
            "code": "match" if identifier in {"a", "b"} else "other",
            "known_at": "2026-01-01T00:00:00+00:00",
        }
        for identifier in identifiers
    ]


@given(events=_events())
def test_count_predicates_are_order_invariant_and_duplicate_idempotent(events: list[dict]) -> None:
    predicate = {
        "op": "count",
        "where": {"op": "event", "equals": {"code": "match"}},
        "min": 2,
    }
    expected = len({item["evidence_id"] for item in events if item["code"] == "match"}) >= 2
    assert evaluate_predicate(predicate, events) is expected
    assert evaluate_predicate(predicate, list(reversed(events))) is expected


@given(day=st.integers(min_value=1, max_value=28))
def test_knowledge_cutoff_never_accepts_later_evidence(day: int) -> None:
    predicate = {
        "op": "event",
        "equals": {"code": "match"},
        "known_before": "2026-01-15T00:00:00+00:00",
    }
    event = {
        "evidence_id": f"event-{day}",
        "code": "match",
        "known_at": f"2026-01-{day:02d}T00:00:00+00:00",
    }
    assert evaluate_predicate(predicate, [event]) is (day <= 15)
