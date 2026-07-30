from __future__ import annotations

from clara_ml.nlp_vi import analyze_clinical_utterance


def test_vietnamese_packet_keeps_negation_experiencer_temporality_and_medication_usage() -> None:
    packet = analyze_clinical_utterance(
        "Mẹ tôi không đau ngực, đang uống para; ngày mai định dùng amoxi.",
        intent="general_health_qa",
    )

    assert packet.implementation == "deterministic_fallback_v1"
    assert packet.experiencer == "family"
    assert "đau ngực" in packet.negated_entities
    assert packet.temporality[0].value == "current"
    assert {item.normalized_candidate for item in packet.medications} == {
        "paracetamol",
        "amoxicillin",
    }


def test_vietnamese_packet_distinguishes_allergy_adverse_effect_lab_and_urgency() -> None:
    packet = analyze_clinical_utterance(
        "Tôi bị dị ứng, buồn nôn; huyết áp 150 mmhg và khó thở.",
    )

    assert {item.category for item in packet.symptoms} >= {"allergy", "adverse_effect"}
    assert packet.labs[0].value == "150"
    assert packet.urgency_signals == ["khó thở"]
