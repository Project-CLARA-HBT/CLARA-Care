"""Regression coverage for CareGuard's additive wording projection."""

from __future__ import annotations

import pytest

from clara_ml.agents import careguard


def test_consumer_wording_is_absent_until_release_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", False)

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    assert "consumer_explanation" not in result


def test_consumer_wording_preserves_final_drugbank_result_and_uses_safe_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", True)

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    rendered = result["consumer_explanation"]
    assert result["risk"]["level"] in {"high", "critical"}
    assert rendered["headline"] == "Nên được nhân viên y tế đánh giá sớm"
    assert rendered["verifier_passed"] is True
    assert rendered["fallback_used"] is False
    assert (
        "warfarin"
        not in " ".join(
            [rendered["headline"], rendered["summary"], *rendered["next_steps"]]
        ).lower()
    )
    # The existing DrugBank/curated alert and recommendation remain untouched.
    assert result["ddi_alerts"]
    assert result["recommendation"]


def test_unavailable_required_drugbank_wording_never_reassures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_wording_renderer_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_required", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", False)

    result = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )

    rendered = result["consumer_explanation"]
    assert result["ddi_status"]["conclusion_available"] is False
    assert rendered["verifier_passed"] is True
    assert "không có cảnh báo không đồng nghĩa là an toàn" in str(rendered["safety_text"]).lower()
    assert rendered["fallback_used"] is False
