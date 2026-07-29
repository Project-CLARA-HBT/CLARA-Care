"""Typed, source-spanned and non-inferential evidence intelligence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

CandidateKind = Literal[
    "pico_population",
    "pico_intervention",
    "pico_comparison",
    "pico_outcome",
    "guideline_condition",
    "trial_criterion",
]
CriterionResult = Literal["match", "mismatch", "unknown"]


class EvidenceIntelligenceError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    source_class: str
    revision: str
    retrieved_at: datetime
    text: str
    checksum: str
    supersedes_source_id: str | None = None


@dataclass(frozen=True)
class ExtractionCandidate:
    kind: CandidateKind
    normalized_key: str
    operator: str
    expected_value: str
    source_id: str
    start: int
    end: int
    quote: str
    confidence: float
    extractor_version: str
    review_state: Literal["awaiting_review"] = "awaiting_review"


class EvidenceExtractor(Protocol):
    extractor_version: str

    def extract(self, *, source_class: str, text: str) -> list[dict[str, Any]]: ...


def extract_review_candidates(
    *,
    source: EvidenceSource,
    extractor: EvidenceExtractor,
) -> tuple[ExtractionCandidate, ...]:
    raw_items = extractor.extract(source_class=source.source_class, text=source.text)
    if not isinstance(raw_items, list) or len(raw_items) > 100:
        raise EvidenceIntelligenceError("evidence_extraction_output_invalid")
    candidates: list[ExtractionCandidate] = []
    allowed_kinds = {
        "pico_population",
        "pico_intervention",
        "pico_comparison",
        "pico_outcome",
        "guideline_condition",
        "trial_criterion",
    }
    for raw in raw_items:
        if not isinstance(raw, dict) or set(raw) != {
            "kind",
            "normalized_key",
            "operator",
            "expected_value",
            "start",
            "end",
            "quote",
            "confidence",
        }:
            raise EvidenceIntelligenceError("evidence_extraction_schema_invalid")
        if raw["kind"] not in allowed_kinds:
            raise EvidenceIntelligenceError("evidence_extraction_kind_invalid")
        candidate = ExtractionCandidate(
            kind=raw["kind"],
            normalized_key=str(raw["normalized_key"]),
            operator=str(raw["operator"]),
            expected_value=str(raw["expected_value"]),
            source_id=source.source_id,
            start=int(raw["start"]),
            end=int(raw["end"]),
            quote=str(raw["quote"]),
            confidence=float(raw["confidence"]),
            extractor_version=extractor.extractor_version,
        )
        validate_extraction_candidate(candidate, source)
        candidates.append(candidate)
    return tuple(candidates)


def validate_extraction_candidate(
    candidate: ExtractionCandidate,
    source: EvidenceSource,
) -> None:
    if (
        candidate.source_id != source.source_id
        or not candidate.normalized_key
        or candidate.operator not in {"equals", "not_equals", "gte", "lte", "contains"}
        or not candidate.expected_value
        or not candidate.extractor_version
        or not 0 <= candidate.confidence <= 1
        or candidate.start < 0
        or candidate.end <= candidate.start
        or candidate.end > len(source.text)
        or source.text[candidate.start : candidate.end] != candidate.quote
        or candidate.review_state != "awaiting_review"
    ):
        raise EvidenceIntelligenceError("evidence_candidate_not_source_grounded")
    if hashlib.sha256(source.text.encode()).hexdigest() != source.checksum:
        raise EvidenceIntelligenceError("evidence_source_checksum_mismatch")


@dataclass(frozen=True)
class ConfirmedFact:
    key: str
    value: str
    revision_id: str
    truth_state: str = "confirmed"


@dataclass(frozen=True)
class CriterionAssessment:
    candidate: ExtractionCandidate
    result: CriterionResult
    fact_revision_id: str | None
    reason: str


def compare_criterion(
    candidate: ExtractionCandidate,
    confirmed_facts: tuple[ConfirmedFact, ...],
) -> CriterionAssessment:
    facts = [
        fact
        for fact in confirmed_facts
        if fact.key == candidate.normalized_key and fact.truth_state == "confirmed"
    ]
    if not facts:
        return CriterionAssessment(
            candidate, "unknown", None, "confirmed_fact_unavailable"
        )
    if len(facts) != 1:
        return CriterionAssessment(
            candidate, "unknown", None, "conflicting_confirmed_facts"
        )
    fact = facts[0]
    actual, expected = fact.value.strip().casefold(), candidate.expected_value.strip().casefold()
    if candidate.operator == "equals":
        matched = actual == expected
    elif candidate.operator == "not_equals":
        matched = actual != expected
    elif candidate.operator == "contains":
        matched = expected in actual
    else:
        try:
            left, right = float(actual), float(expected)
        except ValueError:
            return CriterionAssessment(
                candidate, "unknown", fact.revision_id, "typed_numeric_value_invalid"
            )
        matched = left >= right if candidate.operator == "gte" else left <= right
    return CriterionAssessment(
        candidate,
        "match" if matched else "mismatch",
        fact.revision_id,
        "validated_rule_comparison",
    )


@dataclass(frozen=True)
class CitationAssessment:
    source_id: str
    valid: bool
    current: bool
    contradiction: bool
    reason: str


@dataclass(frozen=True)
class EvidenceReview:
    wording: Literal["possible_match_for_review", "not_assessed"]
    criteria: tuple[CriterionAssessment, ...]
    citations: tuple[CitationAssessment, ...]
    contradiction_present: bool
    clinician_discussion_questions: tuple[str, ...]
    abstained: bool
    disclosure: str


def review_evidence_match(
    *,
    candidates: tuple[ExtractionCandidate, ...],
    sources: tuple[EvidenceSource, ...],
    confirmed_facts: tuple[ConfirmedFact, ...],
    contradiction_pairs: tuple[tuple[str, str], ...] = (),
    discussion_questions: tuple[str, ...] = (),
) -> EvidenceReview:
    source_by_id = {source.source_id: source for source in sources}
    if len(source_by_id) != len(sources):
        raise EvidenceIntelligenceError("evidence_source_id_duplicate")
    criteria: list[CriterionAssessment] = []
    for candidate in candidates:
        source = source_by_id.get(candidate.source_id)
        if source is None:
            raise EvidenceIntelligenceError("citation_source_missing")
        validate_extraction_candidate(candidate, source)
        criteria.append(compare_criterion(candidate, confirmed_facts))

    contradicted_ids = {item for pair in contradiction_pairs for item in pair}
    known_ids = set(source_by_id)
    if not contradicted_ids <= known_ids:
        raise EvidenceIntelligenceError("contradiction_source_missing")
    superseded = {
        source.supersedes_source_id
        for source in sources
        if source.supersedes_source_id is not None
    }
    citation_results = tuple(
        CitationAssessment(
            source_id=source.source_id,
            valid=hashlib.sha256(source.text.encode()).hexdigest() == source.checksum,
            current=source.source_id not in superseded,
            contradiction=source.source_id in contradicted_ids,
            reason=(
                "superseded"
                if source.source_id in superseded
                else "contradicted"
                if source.source_id in contradicted_ids
                else "current"
            ),
        )
        for source in sources
    )
    unknown = any(item.result == "unknown" for item in criteria)
    invalid_citation = any(not item.valid for item in citation_results)
    contradiction = bool(contradicted_ids)
    abstained = unknown or invalid_citation
    if abstained:
        safe_questions: tuple[str, ...] = ()
    else:
        prohibited = ("diagnose", "prescribe", "dose", "start medication", "stop medication")
        safe_questions = tuple(
            question
            for question in discussion_questions
            if question.endswith("?")
            and not any(term in question.casefold() for term in prohibited)
        )
    return EvidenceReview(
        wording="not_assessed" if abstained else "possible_match_for_review",
        criteria=tuple(criteria),
        citations=citation_results,
        contradiction_present=contradiction,
        clinician_discussion_questions=safe_questions,
        abstained=abstained,
        disclosure=(
            "This is a possible evidence match for clinician review, not a "
            "diagnosis, enrollment decision, or treatment recommendation."
        ),
    )
