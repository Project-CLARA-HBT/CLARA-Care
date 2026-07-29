from __future__ import annotations

import pytest

from clara_ml.language_renderer import RenderingInput, render_explanation
from clara_ml.language_renderer.verifier import verify_fidelity


def test_renderer_preserves_emergency_action_and_uncertainty_without_a_score() -> None:
    rendered = render_explanation(
        RenderingInput(
            audience="lay_vi",
            severity="emergency",
            action_codes=["seek_emergency"],
            mandatory_warnings=["Không tự thay đổi thuốc."],
            uncertainty_level="high",
            evidence_labels=["Hướng dẫn đã kiểm tra"],
        )
    )

    visible = " ".join(
        [rendered.headline, rendered.summary, *rendered.next_steps, rendered.uncertainty_text]
    ).lower()
    assert "cấp cứu" in visible
    assert "không thay thế" in visible
    assert "%" not in visible
    assert rendered.verifier_passed is True
    assert rendered.fallback_used is False


def test_verifier_rejects_added_dose_and_missing_mandatory_warning() -> None:
    source = RenderingInput(
        audience="lay_vi",
        severity="clinical_review",
        action_codes=["contact_clinician"],
        mandatory_warnings=["Không tự thay đổi thuốc."],
        uncertainty_level="high",
    )
    candidate = render_explanation(source).model_copy(
        update={
            "safety_text": None,
            "summary": "Hãy uống 500 mg ngay hôm nay.",
        }
    )

    violations = verify_fidelity(source, candidate)

    assert "mandatory_warning_missing" in violations
    assert "dose_text_added" in violations


def test_renderer_does_not_accept_invalid_emergency_contract() -> None:
    with pytest.raises(ValueError, match="seek_emergency"):
        RenderingInput(
            audience="lay_vi",
            severity="emergency",
            action_codes=[],
            uncertainty_level="high",
        )
