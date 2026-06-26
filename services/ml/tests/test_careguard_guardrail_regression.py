"""Medical-safety guardrail regression suite (ML side).

Feature: clara-selfmed-careguard-upgrade (task 11.1)

Pins the *existing* CareGuard guardrails that live in the deterministic ML agent
(``run_careguard_analyze`` and its helpers) so the additive, flag-gated upgrade
can never silently regress them:

* **No prescribing / no definitive diagnosis / no personal dosage** (Req 7.1) —
  no generated recommendation ever echoes a dosage figure, a pill count, or
  prescriptive "take N" instructions, and none asserts a definitive diagnosis.
* **Clinician-review directive preserved** (Req 7.4) — a detected interaction
  yields a recommendation that routes the user to a clinician/pharmacist (or, on
  the emergency fast-path, to urgent care), never a self-treatment instruction.
* **Dosage-token stripping during normalization** (Req 7.5) — dosage units,
  counts, and route/form tokens are stripped before rule matching, so dosage
  figures are never carried into the analysis (and therefore never echoed back).

These guards do not depend on any new flag; they are the pre-feature contract.
External DDI sources are left disabled so the suite is deterministic and never
makes a network call.
"""

from __future__ import annotations

import re

from clara_ml.agents.careguard import (
    _canonicalize_medication_token,
    _recommendation_for,
    run_careguard_analyze,
)

# A dosage figure is a number adjacent to a strength/volume unit, and a pill
# count is "x N". Recommendations are advisory Vietnamese prose and must contain
# no numerals at all, so any digit is a regression toward dosage/quantity advice.
_DIGIT = re.compile(r"\d")
_DOSAGE_TOKEN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|µg|ml|iu|%)\b", re.IGNORECASE)

# Recognized clinician-review / urgent-care directives. A detected interaction
# must always steer the user to a professional, never to self-treatment.
_CLINICIAN_OR_URGENT_TERMS = (
    "bác sĩ",
    "dược sĩ",
    "cơ sở y tế",
    "cấp cứu",
    "đi khám",
)

# Representative alert payloads exercising every branch of ``_recommendation_for``.
_SAMPLE_ALERTS = {
    "bleeding": [{"message": "Nguy cơ chảy máu khi phối hợp.", "severity": "high"}],
    "muscle": [{"message": "Nguy cơ đau cơ / tổn thương cơ.", "severity": "high"}],
    "potassium": [{"message": "Nguy cơ tăng kali máu.", "severity": "high"}],
    "antiplatelet": [
        {"message": "Tương tác với clopidogrel (chống kết tập tiểu cầu).", "severity": "medium"}
    ],
    "drowsy": [{"message": "Có thể gây buồn ngủ, chóng mặt.", "severity": "low"}],
    "generic": [{"message": "Tương tác thuốc tiềm ẩn.", "severity": "high"}],
}


def _all_recommendation_samples() -> list[str]:
    """Every recommendation branch, gathered for the no-dosage/no-diagnosis scan."""
    samples: list[str] = []
    # Emergency fast-path (critical symptom short-circuit).
    samples.append(_recommendation_for("critical", [], ["chest pain"]))
    # Each risk level against each representative alert payload.
    for level in ("critical", "high", "medium", "low"):
        samples.append(_recommendation_for(level, [], []))
        for alerts in _SAMPLE_ALERTS.values():
            samples.append(_recommendation_for(level, alerts, []))
    # No-interaction (empty alert list, low level).
    samples.append(_recommendation_for("low", [], []))
    return samples


# ---------------------------------------------------------------------------
# No prescribing / no definitive diagnosis / no personal dosage (Req 7.1)
# ---------------------------------------------------------------------------


def test_recommendations_never_contain_dosage_figures_or_counts() -> None:
    for recommendation in _all_recommendation_samples():
        assert not _DOSAGE_TOKEN.search(recommendation), (
            f"recommendation leaked a dosage figure: {recommendation!r}"
        )
        # Advisory prose carries no numerals at all; any digit is a regression
        # toward a dose/count/quantity instruction.
        assert not _DIGIT.search(recommendation), (
            f"recommendation leaked a numeric token: {recommendation!r}"
        )


def test_analysis_recommendation_has_no_dosage_for_known_high_risk_pair() -> None:
    result = run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    recommendation = result["recommendation"]
    assert not _DOSAGE_TOKEN.search(recommendation)
    assert not _DIGIT.search(recommendation)


# ---------------------------------------------------------------------------
# Clinician-review directive preserved (Req 7.4)
# ---------------------------------------------------------------------------


def test_detected_interaction_routes_to_clinician_or_urgent_care() -> None:
    result = run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    assert result["ddi_alerts"], "expected a detected interaction for this known pair"
    recommendation = result["recommendation"].lower()
    assert any(term in recommendation for term in _CLINICIAN_OR_URGENT_TERMS), (
        f"interaction recommendation lacks a clinician/urgent-care directive: "
        f"{result['recommendation']!r}"
    )


def test_emergency_fast_path_routes_to_urgent_care_without_diagnosis() -> None:
    recommendation = _recommendation_for("critical", [], ["chest pain"])
    assert "cấp cứu" in recommendation or "cơ sở y tế" in recommendation
    # Fast-path is a routing directive, not a diagnosis or prescription.
    assert not _DIGIT.search(recommendation)


# ---------------------------------------------------------------------------
# Dosage-token stripping during normalization (Req 7.5)
# ---------------------------------------------------------------------------


def test_canonicalize_strips_dosage_units_counts_and_route_form() -> None:
    cases = {
        "warfarin 5mg": "warfarin",
        "ibuprofen 400mg tablet": "ibuprofen",
        "paracetamol 500 mg x 2": "paracetamol",
        "amoxicillin 250mg/5ml suspension": "amoxicillin",
        "aspirin 81 mg tab": "aspirin",
        "metformin 850mg po bid": "metformin",
    }
    for raw, expected in cases.items():
        assert _canonicalize_medication_token(raw) == expected


def test_canonicalized_token_never_retains_numeric_or_unit_residue() -> None:
    for raw in (
        "warfarin 5mg",
        "ibuprofen 400mg tablet",
        "paracetamol 500 mg x 2",
        "amoxicillin 250mg/5ml suspension",
    ):
        canonical = _canonicalize_medication_token(raw)
        assert not _DIGIT.search(canonical), f"dosage digit survived in {canonical!r}"
        assert not _DOSAGE_TOKEN.search(canonical)


def test_decorated_medication_names_still_match_after_dosage_stripping() -> None:
    """Dosage stripping must not break rule matching for the underlying drugs."""
    result = run_careguard_analyze(
        {
            "medications": ["Warfarin 5mg", "Ibuprofen 400mg tablet"],
            "external_ddi_enabled": False,
        }
    )
    ddi_pairs = [set(alert.get("medications", [])) for alert in result["ddi_alerts"]]
    assert any({"warfarin", "ibuprofen"}.issubset(pair) for pair in ddi_pairs)
    # The normalized input carries no dosage residue.
    for entry in result["metadata"]["normalized_inputs"]:
        assert not _DIGIT.search(entry["canonical_input"])
