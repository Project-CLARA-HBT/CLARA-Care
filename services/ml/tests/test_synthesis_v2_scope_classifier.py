"""Property tests for the CLARA Pro synthesis v2 scope classifier (task 2.1).

Feature: ``clara-pro-answer-synthesis``. Task 2.1 introduces the pure, PII-free
``_classify_query_scope`` heuristic that emits a ``(scope_label, scope_factor)``
ScopeSignal (Requirement 1.1). These property tests pin design Correctness
Property **P2 — scope monotonicity** at the classifier level:

    broader scope ⇒ ``scope_factor`` non-decreasing, all else equal.

Because the scope-aware *budget* (task 3.1) multiplies ``scope_factor`` into the
length band monotonically, establishing monotonicity of the factor here is the
load-bearing half of P2. Unit tests for the discrete labels + factor ranges live
in task 2.2; here we exercise the universal monotonicity/closure properties
across arbitrary inputs.

**Validates: Requirements 1.1**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.agents import research_tier2 as rt

from synthesis_v2.harness import PROPERTY_TAGS

# Ensure the property tag this module pins still exists in the design map.
assert "P2" in PROPERTY_TAGS

_NARROW_TOPIC = "Paracetamol là gì?"
_COMPARISON_AUGMENT = (
    " So sánh hiệu quả và an toàn giữa các lựa chọn điều trị, đồng thời "
    "phân tích tuân thủ; chi phí và theo dõi dài hạn ra sao?"
)

# All four scope labels, narrowest → broadest, used to assert the factor map is
# strictly monotonic in scope rank.
_SCOPE_RANK: tuple[str, ...] = ("narrow", "standard", "broad", "comparative_multi")


def _counts() -> st.SearchStrategy[tuple[int, int, int]]:
    return st.tuples(
        st.integers(min_value=0, max_value=200),
        st.integers(min_value=0, max_value=80),
        st.integers(min_value=0, max_value=80),
    )


@given(topic=st.text(max_size=200), counts=_counts())
@settings(max_examples=60)
def test_p2_signal_is_well_formed(topic: str, counts: tuple[int, int, int]) -> None:
    """The ScopeSignal is always a known label with a factor in [0.4, 1.0],
    and the label's canonical factor matches the returned factor."""

    citations, passes, nodes = counts
    label, factor = rt._classify_query_scope(
        topic,
        citation_count=citations,
        deep_pass_count=passes,
        reasoning_node_count=nodes,
    )
    assert label in _SCOPE_RANK
    assert 0.4 <= factor <= 1.0
    assert factor == rt._SCOPE_FACTORS[label]


def test_p2_factor_map_strictly_increases_with_scope_rank() -> None:
    """The label→factor map is monotonic in scope rank (P2 ground truth)."""

    factors = [rt._SCOPE_FACTORS[label] for label in _SCOPE_RANK]
    assert factors == sorted(factors)
    assert len(set(factors)) == len(factors)  # strictly increasing


@given(
    citations=st.integers(min_value=0, max_value=200),
    passes=st.integers(min_value=0, max_value=80),
    nodes=st.integers(min_value=0, max_value=80),
    extra_density=st.integers(min_value=0, max_value=120),
)
@settings(max_examples=60)
def test_p2_more_density_never_lowers_factor(
    citations: int, passes: int, nodes: int, extra_density: int
) -> None:
    """Density monotonicity at the classifier: adding evidence to the *same*
    query never decreases ``scope_factor`` (broader scope ⇒ non-decreasing)."""

    _, factor_low = rt._classify_query_scope(
        _NARROW_TOPIC,
        citation_count=citations,
        deep_pass_count=passes,
        reasoning_node_count=nodes,
    )
    _, factor_high = rt._classify_query_scope(
        _NARROW_TOPIC,
        citation_count=citations + extra_density,
        deep_pass_count=passes,
        reasoning_node_count=nodes,
    )
    assert factor_high >= factor_low


@given(
    citations=st.integers(min_value=0, max_value=120),
    passes=st.integers(min_value=0, max_value=40),
    nodes=st.integers(min_value=0, max_value=40),
)
@settings(max_examples=60)
def test_p2_adding_scope_signal_never_lowers_factor(
    citations: int, passes: int, nodes: int
) -> None:
    """Adding comparison + multi-part intent cues to a query (all else equal)
    never decreases its ``scope_factor`` (broader scope ⇒ non-decreasing)."""

    _, factor_base = rt._classify_query_scope(
        _NARROW_TOPIC,
        citation_count=citations,
        deep_pass_count=passes,
        reasoning_node_count=nodes,
    )
    _, factor_broadened = rt._classify_query_scope(
        _NARROW_TOPIC + _COMPARISON_AUGMENT,
        citation_count=citations,
        deep_pass_count=passes,
        reasoning_node_count=nodes,
    )
    assert factor_broadened >= factor_base
