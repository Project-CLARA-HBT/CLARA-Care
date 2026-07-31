from __future__ import annotations

from clara_ml.agents import careguard
from clara_ml.nlp_vi.schemas import ClinicalSourceSpan, ClinicalUtterance


def test_careguard_uses_only_exact_source_span_candidates(monkeypatch) -> None:
    source = "toi dang dung Panadol Extra"
    start = source.index("Panadol")
    packet = ClinicalUtterance(
        normalized_text=source,
        source_spans=[
            ClinicalSourceSpan(
                category="medication",
                start=start,
                end=start + len("Panadol Extra"),
            )
        ],
        implementation="hybrid_source_spans_v1",
        extractor_model_version="deepseek-v4-flash.task-route.v1",
        extractor_prompt_version="clinical-language-source-spans.vi.v1",
    )
    monkeypatch.setattr(careguard.settings, "clinical_language_llm_extraction_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_clinical_span_augmentation_enabled", True)
    monkeypatch.setattr(careguard, "enrich_clinical_utterance_with_llm", lambda *_args, **_kwargs: packet)

    candidates, metadata = careguard._augment_raw_medications_with_validated_spans([source])

    assert candidates == [source, "Panadol Extra"]
    assert metadata["state"] == "used"
    assert metadata["added_candidate_count"] == 1
    assert "Panadol Extra" not in str(metadata)


def test_careguard_keeps_legacy_candidates_when_span_packet_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(careguard.settings, "clinical_language_llm_extraction_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_clinical_span_augmentation_enabled", True)
    monkeypatch.setattr(
        careguard,
        "enrich_clinical_utterance_with_llm",
        lambda *_args, **_kwargs: ClinicalUtterance(normalized_text="para"),
    )

    candidates, metadata = careguard._augment_raw_medications_with_validated_spans(["para"])

    assert candidates == ["para"]
    assert metadata == {"state": "fallback", "added_candidate_count": 0}
