"""Unit tests for the CLARA Pro synthesis v2 scope classifier (task 2.2).

Feature: ``clara-pro-answer-synthesis``. Task 2.1 introduced the pure, PII-free
``_classify_query_scope`` heuristic returning a ``(scope_label, scope_factor)``
ScopeSignal (Requirement 1.1). The companion property module
(``test_synthesis_v2_scope_classifier.py``) pins the universal monotonicity /
closure behaviour across arbitrary inputs (design Property P2).

This module is the *example-based* half: it pins the **discrete scope labels**
emitted for representative deep_beta queries and the **documented
``scope_factor`` ranges** — that every factor lands in ``[0.4, 1.0]``, matches
its canonical label mapping, and is monotonic in scope rank
(narrow < standard < broad < comparative_multi).

**Validates: Requirements 1.1**
"""

from __future__ import annotations

import pytest

from clara_ml.agents import research_tier2 as rt

from synthesis_v2.harness import (
    BROAD_COMPARATIVE_TOPIC,
    NARROW_TOPIC,
    STANDARD_TOPIC,
)

# Documented ``scope_factor`` envelope (design / docstring): [0.4, 1.0].
_FACTOR_MIN = 0.4
_FACTOR_MAX = 1.0

# Scope labels narrowest → broadest. Encodes the monotonicity rank used below.
_SCOPE_RANK: tuple[str, ...] = ("narrow", "standard", "broad", "comparative_multi")


# ---------------------------------------------------------------------------
# Discrete label classification — one deterministic example per label.
# ---------------------------------------------------------------------------


def test_narrow_definitional_query_is_narrow() -> None:
    """A short definitional query with no evidence density is ``narrow``."""

    label, factor = rt._classify_query_scope(NARROW_TOPIC)
    assert label == "narrow"
    assert factor == rt._SCOPE_FACTORS["narrow"]


def test_single_intervention_with_modest_density_is_standard() -> None:
    """A single-intervention clinical query (not comparison/multi-part/breadth)
    with modest density that clears the narrow floor classifies as ``standard``."""

    label, factor = rt._classify_query_scope(
        STANDARD_TOPIC,
        citation_count=15,  # density 15: clears narrow (<12), below broad (>=40)
    )
    assert label == "standard"
    assert factor == rt._SCOPE_FACTORS["standard"]


def test_high_density_single_intervention_is_broad() -> None:
    """Heavy evidence density alone (>=40) widens a plain query to ``broad``
    without any comparison/multi-part cue."""

    label, factor = rt._classify_query_scope(
        STANDARD_TOPIC,
        citation_count=40,  # density 40 -> broad branch
    )
    assert label == "broad"
    assert factor == rt._SCOPE_FACTORS["broad"]


def test_comparison_plus_multipart_query_is_comparative_multi() -> None:
    """A long, comparative, multi-part query is ``comparative_multi`` (top scope)."""

    label, factor = rt._classify_query_scope(BROAD_COMPARATIVE_TOPIC)
    assert label == "comparative_multi"
    assert factor == rt._SCOPE_FACTORS["comparative_multi"]


def test_comparison_with_high_density_is_comparative_multi() -> None:
    """A short comparison query reaches ``comparative_multi`` once density >= 30."""

    label, _ = rt._classify_query_scope(
        "So sánh A và B",
        citation_count=30,
    )
    assert label == "comparative_multi"


# ---------------------------------------------------------------------------
# scope_factor ranges + canonical mapping.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", _SCOPE_RANK)
def test_canonical_factor_is_within_documented_range(label: str) -> None:
    """Every canonical scope_factor sits inside the documented [0.4, 1.0] band."""

    factor = rt._SCOPE_FACTORS[label]
    assert _FACTOR_MIN <= factor <= _FACTOR_MAX


def test_factor_map_has_exactly_the_four_known_labels() -> None:
    """The classifier's factor map covers precisely the four ranked labels."""

    assert set(rt._SCOPE_FACTORS) == set(_SCOPE_RANK)


def test_range_endpoints_are_pinned_to_narrowest_and_broadest() -> None:
    """The documented range endpoints map to the extreme scope labels:
    narrow -> 0.4 (floor), comparative_multi -> 1.0 (ceiling)."""

    assert rt._SCOPE_FACTORS["narrow"] == _FACTOR_MIN
    assert rt._SCOPE_FACTORS["comparative_multi"] == _FACTOR_MAX


def test_factor_strictly_increases_with_scope_rank() -> None:
    """scope_factor is strictly monotonic across narrow<standard<broad<comparative_multi."""

    factors = [rt._SCOPE_FACTORS[label] for label in _SCOPE_RANK]
    assert factors == sorted(factors)
    assert len(set(factors)) == len(factors)  # strictly increasing, no ties


@pytest.mark.parametrize(
    ("topic", "kwargs", "expected_label"),
    [
        (NARROW_TOPIC, {}, "narrow"),
        (STANDARD_TOPIC, {"citation_count": 15}, "standard"),
        (STANDARD_TOPIC, {"citation_count": 40}, "broad"),
        (BROAD_COMPARATIVE_TOPIC, {}, "comparative_multi"),
    ],
)
def test_returned_factor_always_matches_label_mapping(
    topic: str, kwargs: dict[str, int], expected_label: str
) -> None:
    """For each representative query the returned factor equals the canonical
    mapping for the emitted label and stays inside [0.4, 1.0]."""

    label, factor = rt._classify_query_scope(topic, **kwargs)
    assert label == expected_label
    assert factor == rt._SCOPE_FACTORS[label]
    assert _FACTOR_MIN <= factor <= _FACTOR_MAX
