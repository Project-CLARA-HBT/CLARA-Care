"""Closed-mode contract for Research's non-generative ML acknowledgement."""

from clara_ml.agents import research_tier2


def test_output_mode_gate_is_dark_by_default(monkeypatch) -> None:
    monkeypatch.setattr(research_tier2.settings, "research_output_modes_enabled", False)
    assert research_tier2._normalize_research_output_mode(
        {"output_mode": "professional"}, role="doctor"
    ) is None


def test_output_mode_gate_keeps_consumers_on_plain_language(monkeypatch) -> None:
    monkeypatch.setattr(research_tier2.settings, "research_output_modes_enabled", True)
    assert research_tier2._normalize_research_output_mode(
        {"output_mode": "professional"}, role="normal"
    ) == "plain_language"
    assert research_tier2._normalize_research_output_mode(
        {"output_mode": "professional"}, role="doctor"
    ) == "professional"
