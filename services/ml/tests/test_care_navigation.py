"""Comprehensive unit and regression tests for Care Navigation and Lab Result Explanation.

Covers:
- Deterministic emergency red-flag detection rules for all mandated categories:
  chest pain, acute dyspnea, stroke signs, severe hemorrhage, anaphylaxis, acute suicidal ideation
- Negation handling (negated symptoms do not false-trigger emergencies)
- CareNavigationEngine urgency classifications: EMERGENCY, URGENT, ROUTINE, PHARMACIST, SELF_CARE
- Recommendation rationale citing user-provided facts without returning ranked disease probability lists
- Clinician handoff summary generation
- LabResultExplainer:
  - Takes analyte name, observed value, unit, lab reference range, specimen date
  - Never invents reference ranges if not provided by lab
  - States what test measures, what value indicates, and clarifies that abnormal flag is not a diagnosis
  - Generates questions user can discuss with clinician
  - Enforces numeric fidelity: cannot alter observed value or unit
"""

from __future__ import annotations

import pytest

from clara_ml.care_navigation import (
    CareNavigationEngine,
    EmergencyRedFlagDetector,
    TriageInput,
)
from clara_ml.result_explanation import (
    LabResultExplainer,
    LabResultInput,
    NumericFidelityError,
)

# ===========================================================================
# 1. EmergencyRedFlagDetector Tests
# ===========================================================================


def test_detector_chest_pain_vi_and_en():
    """Detects acute chest pain in Vietnamese and English."""
    res_vi = EmergencyRedFlagDetector.detect("Tôi bị đau tức ngực dữ dội lan ra cánh tay trái")
    assert len(res_vi) >= 1
    assert any(f.category == "chest_pain" for f in res_vi)

    res_en = EmergencyRedFlagDetector.detect(
        "Patient experiences crushing chest pain with substernal pressure"
    )
    assert len(res_en) >= 1
    assert any(f.category == "chest_pain" for f in res_en)


def test_detector_acute_dyspnea():
    """Detects acute dyspnea / shortness of breath."""
    res = EmergencyRedFlagDetector.detect("Bệnh nhân khó thở cấp, không thở được và tím tái")
    assert len(res) >= 1
    assert any(f.category == "acute_dyspnea" for f in res)

    res_en = EmergencyRedFlagDetector.detect("Severe shortness of breath and cannot breathe")
    assert len(res_en) >= 1
    assert any(f.category == "acute_dyspnea" for f in res_en)


def test_detector_stroke_signs():
    """Detects stroke signs (facial droop, unilateral weakness, speech loss)."""
    res = EmergencyRedFlagDetector.detect(
        "Bác tôi bị đột quỵ, méo miệng và yếu liệt nửa người bên trái"
    )
    assert len(res) >= 1
    assert any(f.category == "stroke_signs" for f in res)

    res_en = EmergencyRedFlagDetector.detect(
        "Sudden facial droop and one sided weakness with slurred speech"
    )
    assert len(res_en) >= 1
    assert any(f.category == "stroke_signs" for f in res_en)


def test_detector_severe_hemorrhage():
    """Detects severe hemorrhage / uncontrolled bleeding."""
    res = EmergencyRedFlagDetector.detect("Bệnh nhân nôn ra máu và chảy máu không cầm được")
    assert len(res) >= 1
    assert any(f.category == "severe_hemorrhage" for f in res)

    res_en = EmergencyRedFlagDetector.detect("Massive uncontrolled bleeding and coughing up blood")
    assert len(res_en) >= 1
    assert any(f.category == "severe_hemorrhage" for f in res_en)


def test_detector_anaphylaxis():
    """Detects anaphylaxis / acute airway compromise."""
    res = EmergencyRedFlagDetector.detect(
        "Sau khi tiêm thuốc bị sốc phản vệ, sưng môi lưỡi và nghẹn họng"
    )
    assert len(res) >= 1
    assert any(f.category == "anaphylaxis" for f in res)

    res_en = EmergencyRedFlagDetector.detect(
        "Patient had anaphylaxis with swollen tongue and throat swelling"
    )
    assert len(res_en) >= 1
    assert any(f.category == "anaphylaxis" for f in res_en)


def test_detector_acute_suicidal_ideation():
    """Detects acute suicidal ideation."""
    res = EmergencyRedFlagDetector.detect("Tôi cảm thấy tuyệt vọng, muốn tự tử và có ý định tự sát")
    assert len(res) >= 1
    assert any(f.category == "acute_suicidal_ideation" for f in res)

    res_en = EmergencyRedFlagDetector.detect(
        "Expressing severe suicidal ideation and want to kill myself"
    )
    assert len(res_en) >= 1
    assert any(f.category == "acute_suicidal_ideation" for f in res_en)


def test_detector_negation_handling():
    """Verifies that negated symptoms do not trigger emergency red flags."""
    text = "Bệnh nhân không đau ngực, không khó thở, không bị méo miệng và không có ý định tự sát"
    res = EmergencyRedFlagDetector.detect(text)
    assert len(res) == 0
    assert not EmergencyRedFlagDetector.has_emergency(text)

    text_en = (
        "Patient has no chest pain, denies shortness of breath, and is without suicidal ideation"
    )
    res_en = EmergencyRedFlagDetector.detect(text_en)
    assert len(res_en) == 0


def test_detector_mixed_negation_and_real_emergency():
    """Verifies that if one symptom is negated but another is present, the real one is caught."""
    text = "Tôi không sốt, nhưng bị đau thắt ngực dữ dội"
    res = EmergencyRedFlagDetector.detect(text)
    assert len(res) == 1
    assert res[0].category == "chest_pain"


# ===========================================================================
# 2. CareNavigationEngine Tests
# ===========================================================================


def test_engine_structured_questions():
    """Verifies that structured triage question set is populated and contains mandatory fields."""
    questions = CareNavigationEngine.get_structured_questions()
    assert len(questions) >= 5
    ids = [q.id for q in questions]
    assert "chief_complaint" in ids
    assert "onset_time" in ids
    assert "severity_scale" in ids
    assert "red_flags_check" in ids


def test_engine_emergency_floor_cannot_be_downgraded():
    """Emergency red flags always force EMERGENCY urgency regardless of other fields."""
    t_input = TriageInput(
        symptoms="Bị đau tức ngực và nghẹn thở",
        onset="10 phút trước",
        severity_score=10,
        locale="vi",
    )
    res = CareNavigationEngine.evaluate(t_input)
    assert res.urgency == "EMERGENCY"
    assert res.care_setting_code == "115_er"
    assert len(res.red_flags_detected) >= 1
    assert "115" in res.recommendation or "Cấp cứu" in res.recommendation
    assert res.clinician_handoff_summary.startswith("TÓM TẮT BÀN GIAO CẤP CỨU")


def test_engine_urgent_same_day_clinic():
    """High severity or acute significant symptoms classify as URGENT."""
    t_input = TriageInput(
        symptoms="Sốt cao 39.5 độ C kéo dài 3 ngày kèm đau bụng dữ dội và nôn liên tục",
        onset="3 ngày trước",
        duration="3 ngày",
        severity_score=8,
        answers={"fever_status": "high_fever"},
        known_conditions=["Đái tháo đường type 2"],
        locale="vi",
    )
    res = CareNavigationEngine.evaluate(t_input)
    assert res.urgency == "URGENT"
    assert res.care_setting_code == "same_day_clinic"
    assert "trong ngày" in res.recommendation or "Same-Day" in res.care_setting
    assert any("Sốt" in fact or "đau bụng" in fact for fact in res.cited_facts)


def test_engine_routine_scheduled_visit():
    """Chronic or subacute symptoms (> 1 week) classify as ROUTINE."""
    t_input = TriageInput(
        symptoms="Đau lưng âm ỉ kéo dài hơn 2 tuần nay, muốn đi khám định kỳ",
        onset="2 tuần trước",
        duration="14 ngày",
        severity_score=5,
        answers={"onset_time": "subacute_weeks"},
        locale="vi",
    )
    res = CareNavigationEngine.evaluate(t_input)
    assert res.urgency == "ROUTINE"
    assert res.care_setting_code == "scheduled_visit"
    assert "định kỳ" in res.recommendation or "hẹn" in res.recommendation


def test_engine_pharmacist_otc():
    """Mild common cold or minor symptoms classify as PHARMACIST."""
    t_input = TriageInput(
        symptoms="Bị cảm lạnh, sổ mũi và nghẹt mũi nhẹ",
        onset="Hôm qua",
        duration="1 ngày",
        severity_score=3,
        locale="vi",
    )
    res = CareNavigationEngine.evaluate(t_input)
    assert res.urgency == "PHARMACIST"
    assert res.care_setting_code == "pharmacy_otc"
    assert "nhà thuốc" in res.recommendation.lower() or "dược sĩ" in res.recommendation.lower()


def test_engine_self_care_home_monitoring():
    """Very mild symptoms classify as SELF_CARE."""
    t_input = TriageInput(
        symptoms="Mỏi cơ nhẹ sau khi tập thể dục buổi sáng",
        onset="Sáng nay",
        duration="vài giờ",
        severity_score=1,
        locale="vi",
    )
    res = CareNavigationEngine.evaluate(t_input)
    assert res.urgency == "SELF_CARE"
    assert res.care_setting_code == "home_monitoring"
    assert "tại nhà" in res.recommendation.lower() or "nghỉ ngơi" in res.recommendation.lower()


def test_engine_never_returns_ranked_disease_probabilities():
    """Safety check: Recommendation/rationale must NEVER return ranked disease probability lists."""
    for text in [
        "Sốt ho đau họng 2 ngày",
        "Đau bụng âm ỉ sau ăn",
        "Đau đầu chóng mặt nhẹ",
    ]:
        t_input = TriageInput(symptoms=text, severity_score=4, locale="vi")
        res = CareNavigationEngine.evaluate(t_input)

        # Check for banned probability patterns (e.g. "70% bệnh A", "khả năng 80%", "xác suất", "disease probabilities")
        combined_text = (
            f"{res.recommendation} {res.rationale} {res.clinician_handoff_summary}".lower()
        )
        assert "xác suất bệnh" not in combined_text
        assert "tỷ lệ mắc bệnh:" not in combined_text
        assert "% khả năng" not in combined_text
        assert "% probability" not in combined_text


def test_engine_cites_user_provided_facts():
    """Engine cites key user-provided facts in rationale and cited_facts."""
    t_input = TriageInput(
        symptoms="Đau dạ dày âm ỉ",
        onset="3 ngày trước",
        duration="3 ngày",
        severity_score=6,
        known_conditions=["Viêm loét dạ dày"],
        current_medications=["Omeprazole 20mg"],
        locale="vi",
    )
    res = CareNavigationEngine.evaluate(t_input)
    assert any("Đau dạ dày âm ỉ" in fact for fact in res.cited_facts)
    assert any("3 ngày" in fact for fact in res.cited_facts)
    assert any("6/10" in fact for fact in res.cited_facts)


# ===========================================================================
# 3. LabResultExplainer Tests
# ===========================================================================


def test_lab_explainer_with_reference_range_high():
    """Explains elevated lab result with lab-provided reference range."""
    lab_in = LabResultInput(
        analyte_name="HbA1c",
        observed_value="7.2",
        unit="%",
        reference_range="4.0 - 5.6",
        specimen_date="2026-08-15",
        locale="vi",
    )
    exp = LabResultExplainer.explain(lab_in)
    assert exp.analyte_name == "HbA1c"
    assert exp.observed_value == "7.2"
    assert exp.unit == "%"
    assert exp.reference_range == "4.0 - 5.6"
    assert exp.reference_range_source == "provided_by_lab"
    assert exp.status_flag == "abnormal_high"
    assert "2 đến 3 tháng" in exp.test_purpose or "đường huyết" in exp.test_purpose
    assert "7.2 %" in exp.interpretation_summary or "7.2" in exp.interpretation_summary
    assert "KHÔNG phải là một chẩn đoán" in exp.non_diagnostic_disclaimer
    assert len(exp.questions_for_clinician) >= 2
    assert exp.fidelity_verified is True


def test_lab_explainer_normal_value():
    """Explains normal lab result."""
    lab_in = LabResultInput(
        analyte_name="Creatinine",
        observed_value=68.0,
        unit="µmol/L",
        reference_range="53 - 97",
        locale="vi",
    )
    exp = LabResultExplainer.explain(lab_in)
    assert exp.status_flag == "normal"
    assert "bình thường" in exp.interpretation_summary.lower()
    assert exp.observed_value == "68.0"
    assert exp.unit == "µmol/L"


def test_lab_explainer_without_reference_range_never_invents():
    """When reference range is not provided, does NOT invent one."""
    lab_in = LabResultInput(
        analyte_name="Glucose",
        observed_value="6.5",
        unit="mmol/L",
        reference_range=None,
        locale="vi",
    )
    exp = LabResultExplainer.explain(lab_in)
    assert exp.reference_range is None
    assert exp.reference_range_source == "not_provided"
    assert exp.status_flag == "unspecified"
    assert "KHÔNG kèm khoảng tham chiếu" in exp.interpretation_summary
    assert "6.5 mmol/L" in exp.interpretation_summary


def test_lab_explainer_empty_reference_range():
    """Handles empty or whitespace reference range gracefully."""
    lab_in = LabResultInput(
        analyte_name="ALT (SGPT)",
        observed_value="45",
        unit="U/L",
        reference_range="   ",
        locale="vi",
    )
    exp = LabResultExplainer.explain(lab_in)
    assert exp.reference_range is None
    assert exp.reference_range_source == "not_provided"
    assert exp.status_flag == "unspecified"


def test_lab_explainer_numeric_fidelity_check():
    """Enforces strict numeric fidelity against mutation."""
    lab_in = LabResultInput(
        analyte_name="Glucose",
        observed_value="5.4",
        unit="mmol/L",
        reference_range="3.9 - 6.4",
    )
    exp = LabResultExplainer.explain(lab_in)

    # Valid check passes
    assert LabResultExplainer.verify_fidelity(lab_in, exp) is True

    # Mutating observed_value must trigger NumericFidelityError
    corrupted_exp = exp.model_copy(update={"observed_value": "5.9"})
    with pytest.raises(NumericFidelityError):
        LabResultExplainer.verify_fidelity(lab_in, corrupted_exp)

    # Mutating unit must trigger NumericFidelityError
    corrupted_unit_exp = exp.model_copy(update={"unit": "mg/dL"})
    with pytest.raises(NumericFidelityError):
        LabResultExplainer.verify_fidelity(lab_in, corrupted_unit_exp)


def test_lab_explainer_english_locale():
    """Tests English locale output."""
    lab_in = LabResultInput(
        analyte_name="LDL-Cholesterol",
        observed_value="145",
        unit="mg/dL",
        reference_range="< 100",
        locale="en",
    )
    exp = LabResultExplainer.explain(lab_in)
    assert exp.status_flag == "abnormal_high"
    assert "cholesterol" in exp.test_purpose.lower()
    assert "HIGHER" in exp.interpretation_summary
    assert "NOT a medical diagnosis" in exp.non_diagnostic_disclaimer
    assert len(exp.questions_for_clinician) >= 2
