import hashlib
from datetime import UTC, datetime

import pytest

from clara_ml.lifemap.evidence_intelligence import (
    ConfirmedFact,
    EvidenceIntelligenceError,
    EvidenceSource,
    ExtractionCandidate,
    compare_criterion,
    extract_review_candidates,
    review_evidence_match,
    validate_extraction_candidate,
)


def _source(
    source_id: str = "s1",
    text: str = "Adults aged 18 years or older",
    supersedes: str | None = None,
) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id,
        source_class="trial_registry",
        revision="2026-07-29",
        retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
        text=text,
        checksum=hashlib.sha256(text.encode()).hexdigest(),
        supersedes_source_id=supersedes,
    )


def _candidate(source: EvidenceSource, **overrides: object) -> ExtractionCandidate:
    quote = "18"
    values = {
        "kind": "trial_criterion",
        "normalized_key": "age",
        "operator": "gte",
        "expected_value": "18",
        "source_id": source.source_id,
        "start": source.text.index(quote),
        "end": source.text.index(quote) + len(quote),
        "quote": quote,
        "confidence": 0.9,
        "extractor_version": "structured-extractor-v1",
    }
    values.update(overrides)
    return ExtractionCandidate(**values)  # type: ignore[arg-type]


def test_typed_candidate_requires_exact_source_span_and_checksum() -> None:
    source = _source()
    validate_extraction_candidate(_candidate(source), source)
    with pytest.raises(EvidenceIntelligenceError, match="source_grounded"):
        validate_extraction_candidate(_candidate(source, quote="19"), source)


def test_provider_output_is_bounded_to_typed_source_spanned_review_candidates() -> None:
    class _Extractor:
        extractor_version = "deepseek-structured-v1"

        def extract(self, *, source_class: str, text: str) -> list[dict[str, object]]:
            assert source_class == "trial_registry"
            start = text.index("18")
            return [
                {
                    "kind": "trial_criterion",
                    "normalized_key": "age",
                    "operator": "gte",
                    "expected_value": "18",
                    "start": start,
                    "end": start + 2,
                    "quote": "18",
                    "confidence": 0.91,
                }
            ]

    source = _source()
    candidates = extract_review_candidates(source=source, extractor=_Extractor())
    assert candidates[0].review_state == "awaiting_review"
    assert candidates[0].extractor_version == "deepseek-structured-v1"


def test_rule_comparison_uses_confirmed_fact_and_never_fills_unknown() -> None:
    source = _source()
    candidate = _candidate(source)
    unknown = compare_criterion(candidate, ())
    assert unknown.result == "unknown"
    assert unknown.fact_revision_id is None
    match = compare_criterion(
        candidate, (ConfirmedFact("age", "42", "revision-age-1"),)
    )
    assert match.result == "match"
    assert match.fact_revision_id == "revision-age-1"


def test_review_separates_match_mismatch_unknown_and_possible_match_wording() -> None:
    source = _source()
    review = review_evidence_match(
        candidates=(_candidate(source),),
        sources=(source,),
        confirmed_facts=(ConfirmedFact("age", "42", "revision-age-1"),),
        discussion_questions=("What should I ask the study team?",),
    )
    assert review.wording == "possible_match_for_review"
    assert review.criteria[0].result == "match"
    assert review.clinician_discussion_questions == (
        "What should I ask the study team?",
    )
    assert "not a diagnosis" in review.disclosure


def test_unknown_abstains_and_suppresses_generated_discussion_questions() -> None:
    source = _source()
    review = review_evidence_match(
        candidates=(_candidate(source),),
        sources=(source,),
        confirmed_facts=(),
        discussion_questions=("Should I start medication?",),
    )
    assert review.abstained is True
    assert review.wording == "not_assessed"
    assert review.clinician_discussion_questions == ()


def test_contradiction_and_supersession_are_explicit_without_mutating_facts() -> None:
    old = _source("old")
    current = _source("current", supersedes="old")
    review = review_evidence_match(
        candidates=(_candidate(current),),
        sources=(old, current),
        confirmed_facts=(ConfirmedFact("age", "42", "revision-age-1"),),
        contradiction_pairs=(("old", "current"),),
    )
    citations = {item.source_id: item for item in review.citations}
    assert citations["old"].current is False
    assert citations["old"].contradiction is True
    assert citations["current"].contradiction is True
    assert review.contradiction_present is True
