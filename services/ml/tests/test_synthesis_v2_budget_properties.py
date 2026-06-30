"""Property-based tests for CLARA Pro synthesis v2 word-budget resolution.

Feature: clara-pro-answer-synthesis. These exercise the scope-aware budget
resolver directly so the design's Correctness Properties hold across arbitrary
evidence-density and scope inputs.

- P1 Budget invariant: ``min <= target <= max <= 15000`` for all inputs/config.
- P2 Scope monotonicity: broader scope ⇒ non-decreasing target, all else equal.
- P3 Density monotonicity: more evidence ⇒ non-decreasing target, all else equal.
- P4 Broad-query band: broad+high-density deep_beta yields ``target >= 8000``.
- P5 No-pad floor: narrow+sparse query yields ``target < floor``.
- P8 Flags-off equivalence: with the flag off, the legacy adaptive budget is used.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as app_settings

_HARD_MAX = 15000

_BROAD_TOPIC = (
    "So sánh hiệu quả, an toàn, tuân thủ và chi phí giữa các thuốc điều trị "
    "tăng huyết áp và đái tháo đường ở bệnh nhân cao tuổi có bệnh thận mạn, "
    "đồng thời phân tích tương tác thuốc và theo dõi dài hạn?"
)
_NARROW_TOPIC = "Paracetamol là gì?"


def _with_flag(value: bool):
    """Context-free toggle of the synthesis v2 flag (restored by caller)."""

    previous = app_settings.synthesis_v2_enabled
    app_settings.synthesis_v2_enabled = value
    return previous


@given(
    citations=st.integers(min_value=0, max_value=200),
    passes=st.integers(min_value=0, max_value=80),
    nodes=st.integers(min_value=0, max_value=80),
    topic=st.sampled_from([_BROAD_TOPIC, _NARROW_TOPIC, "Điều trị viêm họng", ""]),
)
@settings(max_examples=120)
def test_p1_budget_invariant(citations: int, passes: int, nodes: int, topic: str) -> None:
    previous = _with_flag(True)
    try:
        min_w, target_w, max_w = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
            topic=topic,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert 0 <= min_w <= target_w <= max_w <= _HARD_MAX


@given(
    citations=st.integers(min_value=0, max_value=120),
    passes=st.integers(min_value=0, max_value=40),
    nodes=st.integers(min_value=0, max_value=40),
)
@settings(max_examples=80)
def test_p3_density_monotonicity(citations: int, passes: int, nodes: int) -> None:
    previous = _with_flag(True)
    try:
        _, target_low, _ = rt._resolve_scope_aware_word_budget(
            scope_factor=0.62,
            scope_label="standard",
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
        )
        _, target_high, _ = rt._resolve_scope_aware_word_budget(
            scope_factor=0.62,
            scope_label="standard",
            citation_count=citations + 25,
            deep_pass_count=passes + 10,
            reasoning_node_count=nodes + 10,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert target_high >= target_low


def test_p2_scope_monotonicity() -> None:
    previous = _with_flag(True)
    try:
        _, target_narrow, _ = rt._resolve_scope_aware_word_budget(
            scope_factor=0.4,
            scope_label="narrow",
            citation_count=8,
            deep_pass_count=2,
            reasoning_node_count=2,
        )
        _, target_broad, _ = rt._resolve_scope_aware_word_budget(
            scope_factor=1.0,
            scope_label="comparative_multi",
            citation_count=8,
            deep_pass_count=2,
            reasoning_node_count=2,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert target_broad >= target_narrow


def test_p4_broad_high_density_reaches_8k() -> None:
    previous = _with_flag(True)
    try:
        min_w, target_w, max_w = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=80,
            deep_pass_count=30,
            reasoning_node_count=20,
            topic=_BROAD_TOPIC,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert target_w >= 8000
    assert max_w <= _HARD_MAX
    assert min_w <= target_w


def test_p5_narrow_sparse_scales_below_floor() -> None:
    previous = _with_flag(True)
    try:
        floor = min(max(int(app_settings.deep_beta_report_min_words), 4000), 12000)
        _, target_w, _ = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=2,
            deep_pass_count=1,
            reasoning_node_count=0,
            topic=_NARROW_TOPIC,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert target_w < floor


def test_p8_flag_off_uses_legacy_budget() -> None:
    # With the flag off, the resolver must return the legacy adaptive budget,
    # identical to calling the legacy path directly.
    previous = _with_flag(False)
    try:
        got = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=40,
            deep_pass_count=12,
            reasoning_node_count=8,
            topic=_BROAD_TOPIC,
        )
        # Recompute the legacy expectation inline (flag still off).
        legacy_min, legacy_target, legacy_max = rt._resolve_report_word_budget("deep_beta")
        density = 40 + 12 + 8
        expected_target = legacy_target
        if density >= 50:
            expected_target = min(legacy_max, max(legacy_target + 1800, int(legacy_target * 1.18)))
        elif density >= 35:
            expected_target = min(legacy_max, max(legacy_target + 900, int(legacy_target * 1.1)))
        expected_target = min(max(expected_target, legacy_min), legacy_max)
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert got == (legacy_min, expected_target, legacy_max)


def test_p10_deep_mode_distinct_from_deep_beta() -> None:
    # deep mode stays the dense-briefing band regardless of the flag.
    previous = _with_flag(True)
    try:
        deep_budget = rt._resolve_adaptive_report_word_budget(
            research_mode="deep",
            citation_count=80,
            deep_pass_count=30,
            reasoning_node_count=20,
            topic=_BROAD_TOPIC,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous
    assert deep_budget == rt._resolve_deep_word_budget()


def test_scope_classifier_labels() -> None:
    broad_label, broad_factor = rt._classify_query_scope(
        _BROAD_TOPIC, citation_count=80, deep_pass_count=30, reasoning_node_count=20
    )
    narrow_label, narrow_factor = rt._classify_query_scope(
        _NARROW_TOPIC, citation_count=2, deep_pass_count=1, reasoning_node_count=0
    )
    assert broad_label in {"broad", "comparative_multi"}
    assert narrow_label == "narrow"
    assert broad_factor >= narrow_factor
