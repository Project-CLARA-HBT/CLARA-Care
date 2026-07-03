"""Flags-off equivalence suite for CLARA Pro synthesis v2 (Properties P8, P10).

Feature: clara-pro-answer-synthesis, task 8.2.

These tests lock the additive contract of the feature: with
``SYNTHESIS_V2_ENABLED=false`` the resolved **budget**, **section contract**, and
**expansion** behavior must equal the pre-feature baseline (Property P8), and
``deep`` mode must stay distinct from ``deep_beta`` regardless of the flag
(Property P10).

They are the dual of ``test_synthesis_v2_budget_properties.py`` /
``test_synthesis_v2_convergence.py`` (which assert the flag-ON behavior). Each
test toggles the flag explicitly and restores it, so the suite is order- and
ambient-config independent. Everything is pure and network-free.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as app_settings


@pytest.fixture(autouse=True)
def _disable_clean_body():
    """Isolate the true pre-feature (legacy dossier) path for this suite.

    Clean-body Pro is the shipped default but DEFERS to an explicit
    ``synthesis_v2`` opt-in; these tests assert the legacy baseline directly, so
    the clean-body default must be off. Restored after every test so no other
    suite inherits the override.
    """

    previous = app_settings.deep_beta_clean_body_enabled
    app_settings.deep_beta_clean_body_enabled = False
    try:
        yield
    finally:
        app_settings.deep_beta_clean_body_enabled = previous

# A broad comparison query (contains "So sánh") so the flag-ON path *would*
# append query-type directives — making the flags-off / flag-on contrast
# non-vacuous.
_COMPARISON_TOPIC = (
    "So sánh hiệu quả và an toàn giữa hai thuốc điều trị tăng huyết áp ở bệnh nhân cao tuổi"
)
_PLAIN_TOPIC = "Điều trị viêm họng cấp"

# The exact legacy deep_beta requirement list (no query-type directives). Mirrors
# the base ``requirements`` built in ``_resolve_report_section_contract`` before
# the flag-gated ``_resolve_query_type_directives`` extension.
_LEGACY_DEEP_BETA_REQUIREMENTS = [
    "- write as a structured clinical dossier / evidence brief with explicit section-by-section traceability",
    "- open with the answer and decision boundary before background context",
    "- keep claim-evidence mapping explicit, including contradictory or counter evidence and how it changes confidence",
    "- include at least one comparative evidence table and one risk-monitoring table when clinically relevant",
    "- when the query compares options, cover adherence, efficacy, safety, feasibility, and cost/access",
    "- include subgroup caveats, uncertainty, and what new evidence could shift the recommendation",
    "- do not expose internal pipeline tags, execution steps, or debug telemetry in the answer body",
]


def _set_flag(value: bool) -> bool:
    """Set the synthesis v2 flag, returning the previous value for restore."""

    previous = app_settings.synthesis_v2_enabled
    app_settings.synthesis_v2_enabled = value
    return previous


def _legacy_adaptive_budget(
    *,
    citation_count: int,
    deep_pass_count: int,
    reasoning_node_count: int,
) -> tuple[int, int, int]:
    """Recompute the pre-feature adaptive deep_beta budget inline.

    This is the exact arithmetic the flag-OFF branch of
    ``_resolve_adaptive_report_word_budget`` performs, reproduced here so the
    equivalence assertion compares against an independent baseline rather than
    the function under test.
    """

    legacy_min, legacy_target, legacy_max = rt._resolve_report_word_budget("deep_beta")
    density = max(0, citation_count) + max(0, deep_pass_count) + max(0, reasoning_node_count)
    expected_target = legacy_target
    if density >= 50:
        expected_target = min(legacy_max, max(legacy_target + 1800, int(legacy_target * 1.18)))
    elif density >= 35:
        expected_target = min(legacy_max, max(legacy_target + 900, int(legacy_target * 1.1)))
    expected_target = min(max(expected_target, legacy_min), legacy_max)
    return legacy_min, expected_target, legacy_max


# ---------------------------------------------------------------------------
# P8 — Budget equivalence (flag off == legacy adaptive budget)
# ---------------------------------------------------------------------------


@given(
    citations=st.integers(min_value=0, max_value=200),
    passes=st.integers(min_value=0, max_value=80),
    nodes=st.integers(min_value=0, max_value=80),
    topic=st.sampled_from([_COMPARISON_TOPIC, _PLAIN_TOPIC, "Paracetamol là gì?", ""]),
)
@settings(max_examples=150)
def test_p8_flags_off_budget_equals_legacy_adaptive(
    citations: int, passes: int, nodes: int, topic: str
) -> None:
    """With the flag off, the resolved deep_beta budget equals the legacy
    adaptive budget for every input — and is independent of the topic (the
    scope classifier is never consulted on the legacy path)."""

    previous = _set_flag(False)
    try:
        got = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
            topic=topic,
        )
        expected = _legacy_adaptive_budget(
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
        )
        # Topic must not move the budget when the flag is off.
        got_other_topic = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
            topic="So sánh nhiều phác đồ điều trị phức tạp và đa yếu tố",
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert got == expected
    assert got == got_other_topic


# ---------------------------------------------------------------------------
# P8 — Section-contract equivalence (flag off == legacy fixed dossier)
# ---------------------------------------------------------------------------


def test_p8_flags_off_section_contract_is_legacy_and_topic_independent() -> None:
    """Flag off ⇒ the deep_beta section contract is the legacy fixed dossier:
    no query-type directives are appended, and it is identical regardless of
    the topic supplied."""

    previous = _set_flag(False)
    try:
        sections_a, requirements_a = rt._resolve_report_section_contract(
            "deep_beta", answer_language="vi", topic=_COMPARISON_TOPIC
        )
        sections_b, requirements_b = rt._resolve_report_section_contract(
            "deep_beta", answer_language="vi", topic=_PLAIN_TOPIC
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    # Legacy requirement list, byte-for-byte, with no v2 directives appended.
    assert requirements_a == _LEGACY_DEEP_BETA_REQUIREMENTS
    # A comparison topic must not change the contract while the flag is off.
    assert requirements_a == requirements_b
    assert sections_a == sections_b
    assert sections_a == rt._resolve_deep_beta_dossier_headings("vi")


def test_flag_on_section_contract_adds_directives_nonvacuous() -> None:
    """Non-vacuity guard: the flag really gates the directives. With the flag
    ON, a comparison topic appends query-type directives, so the contract is a
    strict superset of the legacy one (otherwise P8's equivalence would be
    trivially true)."""

    previous = _set_flag(True)
    try:
        _, requirements_on = rt._resolve_report_section_contract(
            "deep_beta", answer_language="vi", topic=_COMPARISON_TOPIC
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert requirements_on[: len(_LEGACY_DEEP_BETA_REQUIREMENTS)] == _LEGACY_DEEP_BETA_REQUIREMENTS
    assert len(requirements_on) > len(_LEGACY_DEEP_BETA_REQUIREMENTS)


# ---------------------------------------------------------------------------
# P10 — deep mode distinct from deep_beta, in both flag states
# ---------------------------------------------------------------------------


@given(
    citations=st.integers(min_value=0, max_value=120),
    passes=st.integers(min_value=0, max_value=40),
    nodes=st.integers(min_value=0, max_value=40),
    flag=st.booleans(),
)
@settings(max_examples=80)
def test_p10_deep_stays_distinct_from_deep_beta(
    citations: int, passes: int, nodes: int, flag: bool
) -> None:
    """``deep`` mode resolves to the fixed dense-briefing band regardless of the
    flag or evidence density, and is always strictly below the deep_beta band —
    the two modes never collapse into each other."""

    previous = _set_flag(flag)
    try:
        deep_budget = rt._resolve_adaptive_report_word_budget(
            research_mode="deep",
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
            topic=_COMPARISON_TOPIC,
        )
        deep_beta_budget = rt._resolve_adaptive_report_word_budget(
            research_mode="deep_beta",
            citation_count=citations,
            deep_pass_count=passes,
            reasoning_node_count=nodes,
            topic=_COMPARISON_TOPIC,
        )
    finally:
        app_settings.synthesis_v2_enabled = previous

    # deep is the fixed dense-briefing band, never the adaptive deep_beta band.
    assert deep_budget == rt._resolve_deep_word_budget()
    # deep_beta is a materially longer envelope than deep, in either flag state.
    assert deep_beta_budget[1] > deep_budget[1]
    assert deep_beta_budget[2] > deep_budget[2]


# ---------------------------------------------------------------------------
# P8 — Expansion-loop equivalence (flag off == legacy break-on-first-empty)
# ---------------------------------------------------------------------------


@dataclass
class _StubResponse:
    content: str


class _CountingStubClient:
    """A real first report, then empty continuations, counting generate calls.

    Mirrors the stub in ``test_synthesis_v2_convergence.py`` so the flags-off
    expansion behavior can be asserted to equal the legacy path (break on the
    first empty continuation) without reaching across test modules.
    """

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, prompt: str, system_prompt: str, max_tokens: int = 0) -> _StubResponse:
        self.calls += 1
        if self.calls == 1:
            return _StubResponse(
                content=(
                    "## Kết luận nhanh\nBáo cáo cơ sở để kiểm thử vòng hội tụ ở chế độ "
                    "tổng hợp CLARA Pro với nội dung lâm sàng mẫu.\n\n"
                    "## Phân tích chi tiết\nNội dung phân tích mẫu cho mục đích kiểm thử.\n"
                )
            )
        return _StubResponse(content="")


def test_p8_flags_off_expansion_breaks_on_first_empty_like_legacy(monkeypatch) -> None:
    """With the flag off, the convergence loop stops on the first empty
    continuation (1 initial + 1 empty = 2 generate calls) — the pre-feature
    behavior — instead of rotating through expansion directives."""

    stub = _CountingStubClient()
    monkeypatch.setattr(
        rt,
        "_resolve_adaptive_report_word_budget",
        lambda **_kwargs: (8000, 10000, 12000),
    )
    monkeypatch.setattr(
        rt,
        "_resolve_runtime_llm_config",
        lambda _runtime: ("deepseek", "test-key", "http://x/v1", "deepseek-test"),
    )
    monkeypatch.setattr(rt, "_build_reasoning_client", lambda **_kwargs: stub)

    previous_flag = app_settings.synthesis_v2_enabled
    previous_llm_enabled = app_settings.deep_beta_report_llm_enabled
    app_settings.synthesis_v2_enabled = False
    app_settings.deep_beta_report_llm_enabled = True
    try:
        rt._synthesize_deep_beta_long_report(
            topic="So sánh hai thuốc điều trị tăng huyết áp",
            answer_markdown="## Kết luận nhanh\nCâu trả lời cơ sở.\n",
            citations=[],
            verification_matrix_payload={},
            reasoning_nodes=[],
            deep_pass_summaries=[],
            evidence_verification={},
            llm_runtime={"api_key": "test-key"},
            research_mode="deep_beta",
            answer_language="vi",
        )
    finally:
        app_settings.synthesis_v2_enabled = previous_flag
        app_settings.deep_beta_report_llm_enabled = previous_llm_enabled

    assert stub.calls == 2
