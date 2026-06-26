"""Style-profile variation + anti-repetition directives (Requirement 3.2).

Feature: clara-pro-answer-synthesis, task 4.2.

These tests lock the additive, flag-gated contract of the de-templating style
profile: with ``SYNTHESIS_V2_ENABLED=false`` the deep_beta style profile is the
legacy dict byte-for-byte (Property P8 / Requirement 6.2); with the flag ON it
gains a per-query-type ``style_variation`` block carrying anti-repetition
directives that vary by scope. Everything is pure and network-free.
"""

from __future__ import annotations

from clara_ml.agents import research_tier2 as rt
from clara_ml.config import settings as app_settings

_COMPARISON_TOPIC = (
    "So sánh hiệu quả và an toàn giữa hai thuốc điều trị tăng huyết áp ở bệnh nhân cao tuổi"
)
_NARROW_TOPIC = "Paracetamol là gì?"
_DIAGNOSTIC_TOPIC = "Tiếp cận chẩn đoán phân biệt triệu chứng đau ngực cấp"

_LEGACY_DEEP_BETA_PROFILE = {
    "tone": "clinical_dossier_evidence_brief",
    "narrative_density": "very_high",
    "target_reader": "clinician, researcher, or medical operator who needs a traceable long-form synthesis",
    "must_do": [
        "Lead with the answer and decision boundary, then show the evidence chain explicitly.",
        "Keep claim-evidence linkage explicit and include contradiction handling in a dedicated section.",
        "Translate uncertainty into concrete decision boundaries, subgroup caveats, and monitoring steps.",
        "Use structured clinical headings that make evidence provenance and applicability auditable.",
    ],
    "avoid": [
        "Do not expose internal system nodes, debug steps, or planner tags.",
        "Do not repeat identical sentence openings across adjacent paragraphs.",
        "Do not collapse the report into short Perplexity-style summary-only prose.",
    ],
}


def _set_flag(value: bool) -> bool:
    previous = app_settings.synthesis_v2_enabled
    app_settings.synthesis_v2_enabled = value
    return previous


def test_flags_off_style_profile_is_legacy_and_topic_independent() -> None:
    """Flag off ⇒ the deep_beta style profile is the legacy dict with no
    style_variation block, regardless of topic (Property P8)."""

    previous = _set_flag(False)
    try:
        profile_a = rt._resolve_report_style_profile("deep_beta", topic=_COMPARISON_TOPIC)
        profile_b = rt._resolve_report_style_profile("deep_beta", topic=_NARROW_TOPIC)
        # Legacy positional call must still work and match.
        profile_positional = rt._resolve_report_style_profile("deep_beta")
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert profile_a == _LEGACY_DEEP_BETA_PROFILE
    assert profile_a == profile_b
    assert profile_positional == _LEGACY_DEEP_BETA_PROFILE
    assert "style_variation" not in profile_a


def test_flag_on_style_profile_adds_anti_repetition_directives() -> None:
    """Flag on ⇒ deep_beta gains a style_variation block with anti-repetition
    directives, while the legacy keys remain a superset (non-vacuous)."""

    previous = _set_flag(True)
    try:
        profile = rt._resolve_report_style_profile("deep_beta", topic=_COMPARISON_TOPIC)
    finally:
        app_settings.synthesis_v2_enabled = previous

    # Legacy keys preserved.
    for key, value in _LEGACY_DEEP_BETA_PROFILE.items():
        assert profile[key] == value

    variation = profile["style_variation"]
    # The comparison topic (no density counts) classifies as "broad".
    assert variation["framing"] == "thematic_dossier"
    assert variation["opening_strategy"]
    assert variation["anti_repetition"] == rt._ANTI_REPETITION_DIRECTIVES
    assert any("consecutive paragraphs" in d for d in variation["anti_repetition"])


def test_flag_on_style_variation_varies_by_query_type() -> None:
    """The framing varies by query type so reports do not share one skeleton."""

    previous = _set_flag(True)
    try:
        comparative = rt._resolve_report_style_profile("deep_beta", topic=_COMPARISON_TOPIC)
        narrow = rt._resolve_report_style_profile("deep_beta", topic=_NARROW_TOPIC)
        diagnostic = rt._resolve_report_style_profile("deep_beta", topic=_DIAGNOSTIC_TOPIC)
    finally:
        app_settings.synthesis_v2_enabled = previous

    framings = {
        comparative["style_variation"]["framing"],
        narrow["style_variation"]["framing"],
        diagnostic["style_variation"]["framing"],
    }
    # At least three distinct framings across these query types.
    assert len(framings) == 3
    assert diagnostic["style_variation"]["framing"] == "differential_workup"


def test_non_deep_beta_style_profile_unaffected_by_flag() -> None:
    """deep mode never gains a style_variation block, in either flag state."""

    previous = _set_flag(True)
    try:
        deep_profile = rt._resolve_report_style_profile("deep", topic=_COMPARISON_TOPIC)
    finally:
        app_settings.synthesis_v2_enabled = previous

    assert deep_profile["tone"] == "clinical_briefing_reader_first"
    assert "style_variation" not in deep_profile
