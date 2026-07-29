from clara_ml.nlp.vietnamese_clinical import (
    analyze_vietnamese_clinical_text,
    fold_vietnamese_for_matching,
)


def test_vietnamese_clinical_analysis_handles_typo_negation_experiencer_and_units():
    analysis = analyze_vietnamese_clinical_text(
        "Mẹ tôi ko khó thở, đang uống Panadol 500mg hôm nay"
    )

    assert analysis.normalized_text == "mẹ tôi không khó thở đang uống panadol 500mg hôm nay"
    assert analysis.negated is True
    assert analysis.experiencer == "other"
    assert analysis.temporality == "current"
    assert analysis.units == ("500mg",)
    assert analysis.medication_mentions[0].normalized_candidate == "paracetamol"


def test_fold_vietnamese_preserves_emergency_keyword_matching_without_losing_source():
    assert fold_vietnamese_for_matching("Đột quỵ, đau dữ dội") == "dot quy, dau du doi"


def test_vietnamese_clinical_analysis_marks_planned_medication_as_not_current():
    analysis = analyze_vietnamese_clinical_text("Tôi định uống amox 250 mg ngày mai")

    assert analysis.temporality == "planned"
    assert analysis.experiencer == "self_or_unspecified"
    assert analysis.medication_mentions[0].normalized_candidate == "amoxicillin"
