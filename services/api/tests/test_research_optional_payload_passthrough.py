from __future__ import annotations

from clara_api.api.v1.endpoints import research as research_endpoints

# The additive, flag-gated Tier2 result fields emitted by the ML orchestrator (task 1.2).
_OPTIONAL_TIER2_FIELDS = {
    "citation_registry",
    "traced_claims",
    "pico",
    "grade",
    "consensus",
    "conflicting_evidence",
    "subquestions",
    "gap_fill_passes",
    "output_profile",
    "disclaimer_present",
}


def _ml_result_with_optional_fields() -> dict:
    return {
        "tier": "tier2",
        "research_mode": "deep",
        "answer": "noi dung",
        "answer_markdown": "noi dung",
        "citations": [
            {
                "source_id": "c1",
                "source": "pubmed",
                "title": "A study",
                "url": "https://example.org/a",
                "relevance": "high",
                "study_id": "PMID:12345678",
                "source_type": "systematic_review",
                "trust_tier": 1,
                "published_at": "2023-04-01",
            }
        ],
        "citation_registry": [{"citation_id": "c1", "study_id": "PMID:12345678"}],
        "traced_claims": [
            {"claim": "x", "citation_ids": ["c1"], "verdict": "supported"}
        ],
        "pico": {"population": "p", "intervention": "i", "comparison": "c", "outcome": "o"},
        "grade": [{"claim": "x", "certainty": "moderate"}],
        "consensus": [{"claim": "x", "support": 3, "contrast": 1, "neutral": 0}],
        "conflicting_evidence": [{"claim": "x", "contrasting_citation_ids": ["c5"]}],
        "subquestions": ["q1", "q2"],
        "gap_fill_passes": 2,
        "output_profile": "doctor",
        "disclaimer_present": True,
    }


def test_canonicalize_preserves_optional_tier2_fields():
    result = _ml_result_with_optional_fields()
    canonical = research_endpoints._canonicalize_research_payload_contract(result)
    for key in _OPTIONAL_TIER2_FIELDS:
        assert key in canonical, f"{key} was dropped by canonicalization"
    assert canonical["subquestions"] == ["q1", "q2"]
    assert canonical["gap_fill_passes"] == 2
    assert canonical["output_profile"] == "doctor"
    assert canonical["disclaimer_present"] is True


def test_canonicalize_preserves_per_citation_provenance_fields():
    result = _ml_result_with_optional_fields()
    canonical = research_endpoints._canonicalize_research_payload_contract(result)
    citation = canonical["citations"][0]
    assert citation["study_id"] == "PMID:12345678"
    assert citation["source_type"] == "systematic_review"
    assert citation["trust_tier"] == 1
    assert citation["published_at"] == "2023-04-01"


def test_attach_attribution_preserves_optional_tier2_fields():
    result = _ml_result_with_optional_fields()
    enriched = research_endpoints._attach_research_attribution(result)
    for key in _OPTIONAL_TIER2_FIELDS:
        assert key in enriched, f"{key} was dropped by attribution enrichment"
    # Per-citation provenance also survives the full enrichment path.
    citation = enriched["citations"][0]
    assert citation["study_id"] == "PMID:12345678"
    assert citation["trust_tier"] == 1


def test_legacy_result_without_optional_fields_stays_legacy_shaped():
    legacy = {
        "tier": "tier2",
        "research_mode": "deep",
        "answer": "noi dung",
        "answer_markdown": "noi dung",
        "citations": [
            {
                "source_id": "c1",
                "source": "pubmed",
                "title": "A study",
                "url": "https://example.org/a",
                "relevance": "high",
            }
        ],
    }
    canonical = research_endpoints._canonicalize_research_payload_contract(legacy)
    # No additive Tier2 keys are invented when the ML layer did not emit them.
    assert _OPTIONAL_TIER2_FIELDS.isdisjoint(set(canonical))
    # No additive per-citation provenance keys are invented either.
    citation = canonical["citations"][0]
    assert set(citation) == {"source_id", "source", "title", "url", "relevance"}
