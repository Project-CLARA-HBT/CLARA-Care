"""Unit tests for the StructuredExtractor (task 4.3, Requirement 13.1-13.7).

Covers per-category extraction with span+method provenance, RxCUI mapping via the
RAG drug lexicon (with graceful degradation), empty/no-fabrication when a type is
absent, the flag-off no-op path, the no-mutation invariant, and that every emitted
item's provenance resolves in the shared span registry from task 4.1.
"""

from __future__ import annotations

import copy

from clara_ml.scribe.asr.base import AsrSegment
from clara_ml.scribe.extraction import (
    ExtractedItem,
    ExtractedVital,
    StructuredExtraction,
    StructuredExtractor,
)
from clara_ml.scribe.provenance import build_span_registry


def _segments() -> list[AsrSegment]:
    return [
        AsrSegment(text="Patient has a history of hypertension and diabetes.", speaker="patient"),
        AsrSegment(text="Patient is allergic to penicillin.", speaker="patient"),
        AsrSegment(text="Start lisinopril 10mg once daily.", speaker="clinician"),
        AsrSegment(text="Blood pressure is 120/80 and heart rate 72 bpm today.", speaker="clinician"),
    ]


def _registry(segments: list[AsrSegment] | None = None):
    return build_span_registry(segments if segments is not None else _segments())


def _all_span_ids(extraction: StructuredExtraction) -> list[str]:
    ids: list[str] = []
    for group in (extraction.problems, extraction.medications, extraction.allergies, extraction.vitals):
        for item in group:
            ids.extend(item.provenance.span_ids)
    return ids


# --- flag-off no-op (Req 13.1) --------------------------------------------


def test_flag_off_is_inert_noop() -> None:
    extractor = StructuredExtractor(enabled=False)
    extraction = extractor.extract(_registry())
    assert isinstance(extraction, StructuredExtraction)
    assert extraction.enabled is False
    assert extraction.problems == []
    assert extraction.medications == []
    assert extraction.allergies == []
    assert extraction.vitals == []
    assert extraction.as_dict()["enabled"] is False


# --- problems (Req 13.2/13.3) ---------------------------------------------


def test_extracts_problems_with_span_and_method_provenance() -> None:
    extraction = StructuredExtractor(enabled=True).extract(_registry())
    surfaces = [p.surface.lower() for p in extraction.problems]
    assert "hypertension" in surfaces
    assert "diabetes" in surfaces
    for problem in extraction.problems:
        assert isinstance(problem, ExtractedItem)
        assert problem.provenance.method == "regex"
        assert problem.provenance.span_ids


# --- medications + RxCUI (Req 13.2/13.4) -----------------------------------


def test_extracts_medication_with_rxcui_from_lexicon() -> None:
    extraction = StructuredExtractor(enabled=True).extract(_registry())
    meds = {m.surface.lower(): m for m in extraction.medications}
    assert "lisinopril" in meds
    lisinopril = meds["lisinopril"]
    assert lisinopril.rxcui == "29046"  # RxNorm ingredient id from the lexicon
    assert lisinopril.provenance.method == "lexicon"
    assert lisinopril.provenance.span_ids


def test_unknown_medication_degrades_to_surface_with_null_rxcui() -> None:
    # "cefuroxime" is not in the curated lexicon; the dose context still detects
    # it as a medication and it degrades gracefully to surface text (rxcui=None).
    segments = [AsrSegment(text="Start cefuroxime 250mg twice daily.")]
    extraction = StructuredExtractor(enabled=True).extract(_registry(segments))
    meds = {m.surface.lower(): m for m in extraction.medications}
    assert "cefuroxime" in meds
    assert meds["cefuroxime"].rxcui is None
    assert meds["cefuroxime"].provenance.method == "regex"


def test_brand_alias_resolves_to_lexicon_rxcui() -> None:
    segments = [AsrSegment(text="Patient takes Plavix daily.")]
    extraction = StructuredExtractor(enabled=True).extract(_registry(segments))
    meds = {m.surface.lower(): m for m in extraction.medications}
    assert "plavix" in meds
    assert meds["plavix"].rxcui == "32968"  # clopidogrel ingredient id


# --- allergies (Req 13.2/13.3) + negation no-fabrication -------------------


def test_extracts_allergy_with_provenance() -> None:
    extraction = StructuredExtractor(enabled=True).extract(_registry())
    surfaces = [a.surface.lower() for a in extraction.allergies]
    assert "penicillin" in surfaces
    for allergy in extraction.allergies:
        assert isinstance(allergy, ExtractedItem)
        assert allergy.provenance.method == "regex"
        assert allergy.provenance.span_ids


def test_negated_allergy_is_not_fabricated() -> None:
    segments = [AsrSegment(text="No known drug allergies. Patient denies allergic to anything.")]
    extraction = StructuredExtractor(enabled=True).extract(_registry(segments))
    assert extraction.allergies == []


# --- vitals (Req 13.2/13.3) ------------------------------------------------


def test_extracts_vitals_with_kind_value_and_provenance() -> None:
    extraction = StructuredExtractor(enabled=True).extract(_registry())
    by_kind = {v.kind: v for v in extraction.vitals}
    assert "blood_pressure" in by_kind
    assert by_kind["blood_pressure"].value == "120/80"
    assert "heart_rate" in by_kind
    assert by_kind["heart_rate"].value == "72"
    for vital in extraction.vitals:
        assert isinstance(vital, ExtractedVital)
        assert vital.provenance.method == "regex"
        assert vital.provenance.span_ids


# --- no fabrication when a type is absent (Req 13.7) -----------------------


def test_absent_types_yield_empty_lists() -> None:
    segments = [AsrSegment(text="Patient feels generally well and has no specific concerns.")]
    extraction = StructuredExtractor(enabled=True).extract(_registry(segments))
    assert extraction.problems == []
    assert extraction.medications == []
    assert extraction.allergies == []
    assert extraction.vitals == []


# --- shared span registry: every item resolves (Req 13.3/13.6) -------------


def test_every_item_provenance_resolves_in_shared_registry() -> None:
    registry = _registry()
    extraction = StructuredExtractor(enabled=True).extract(registry)
    span_ids = _all_span_ids(extraction)
    assert span_ids  # something was extracted
    for span_id in span_ids:
        assert registry.resolve(span_id) is not None


# --- no mutation of transcript (Req 13.5) ----------------------------------


def test_extract_never_mutates_transcript_segments() -> None:
    segments = _segments()
    snapshot = copy.deepcopy(segments)
    registry = build_span_registry(segments)
    StructuredExtractor(enabled=True).extract(registry)
    assert segments == snapshot
    assert [s.text for s in segments] == [s.text for s in snapshot]


# --- serialization is additive + clean ------------------------------------


def test_as_dict_is_serializable_and_complete() -> None:
    extraction = StructuredExtractor(enabled=True).extract(_registry())
    payload = extraction.as_dict()
    assert payload["version"] == "scribe-extraction-v1"
    assert payload["enabled"] is True
    assert set(payload) == {"version", "enabled", "problems", "medications", "allergies", "vitals"}
    med = next(m for m in payload["medications"] if m["surface"].lower() == "lisinopril")
    assert med["rxcui"] == "29046"
    assert med["method"] == "lexicon"
    assert med["span_ids"]


def test_injected_lexicon_lookup_is_used() -> None:
    calls: list[str] = []

    def fake_lookup(surface: str):
        calls.append(surface)
        return None

    segments = [AsrSegment(text="Start aspirin 100mg daily.")]
    extraction = StructuredExtractor(enabled=True, lexicon_lookup=fake_lookup).extract(
        _registry(segments)
    )
    # Lexicon never resolves -> aspirin only surfaces via the dose-context scan.
    assert calls  # the injected resolver was consulted
    meds = {m.surface.lower(): m for m in extraction.medications}
    assert "aspirin" in meds
    assert meds["aspirin"].rxcui is None
