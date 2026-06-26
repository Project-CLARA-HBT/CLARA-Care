from __future__ import annotations

from dataclasses import asdict

from clara_ml.agents import research_tier2 as tier2
from clara_ml.agents.research_tier2 import Citation, PicoFrame


# --- Citation payload: additive provenance fields omitted when unset (R6.2, R11.2, R20.2) ---

_LEGACY_CITATION_KEYS = {"source_id", "source", "title", "url", "relevance"}


def _legacy_citation() -> Citation:
    return Citation(
        source_id="s1",
        source="pubmed",
        title="A study",
        url="https://example.org/a",
        relevance="high",
    )


def test_citation_as_payload_omits_unset_provenance_fields():
    payload = tier2._citation_as_payload(_legacy_citation())
    # Legacy shape preserved byte-for-byte: no new keys leak when unset.
    assert set(payload) == _LEGACY_CITATION_KEYS
    for key in tier2._OPTIONAL_CITATION_KEYS:
        assert key not in payload


def test_citation_as_payload_includes_provenance_fields_when_set():
    citation = Citation(
        source_id="s1",
        source="pubmed",
        title="A study",
        url="https://example.org/a",
        relevance="high",
        study_id="PMID:12345678",
        source_type="systematic_review",
        trust_tier=1,
        published_at="2023-04-01",
    )
    payload = tier2._citation_as_payload(citation)
    assert payload["study_id"] == "PMID:12345678"
    assert payload["source_type"] == "systematic_review"
    assert payload["trust_tier"] == 1
    assert payload["published_at"] == "2023-04-01"
    # Legacy keys still present alongside the additive ones.
    assert _LEGACY_CITATION_KEYS <= set(payload)


def test_citation_as_payload_partial_provenance_only_includes_set_fields():
    citation = Citation(
        source_id="s1",
        source="pubmed",
        title="A study",
        url="https://example.org/a",
        relevance="high",
        trust_tier=2,
    )
    payload = tier2._citation_as_payload(citation)
    assert payload["trust_tier"] == 2
    # The other provenance keys remain omitted because they are unset.
    assert "study_id" not in payload
    assert "source_type" not in payload
    assert "published_at" not in payload


def test_citation_dataclass_defaults_preserve_legacy_construction():
    # A Citation built with only the legacy positional args still constructs and the
    # new fields default to None (so asdict carries them, but the payload strips them).
    citation = _legacy_citation()
    raw = asdict(citation)
    for key in tier2._OPTIONAL_CITATION_KEYS:
        assert raw[key] is None


# --- Optional Tier2 payload builder: keys present only when produced (R20.2) ----------------


def test_build_tier2_optional_payload_empty_when_no_artifacts():
    # Flags off / nothing produced -> no additive keys, legacy result shape preserved.
    assert tier2._build_tier2_optional_payload() == {}


def test_build_tier2_optional_payload_includes_pico_when_present():
    frame = PicoFrame(
        population="người cao tuổi",
        intervention="warfarin",
        comparison="aspirin",
        outcome="xuất huyết",
    )
    payload = tier2._build_tier2_optional_payload(pico_frame=frame)
    assert payload == {"pico": frame.as_payload()}


def test_build_tier2_optional_payload_carries_every_field_when_supplied():
    payload = tier2._build_tier2_optional_payload(
        pico_frame=PicoFrame(
            population="p", intervention="i", comparison="c", outcome="o"
        ),
        citation_registry=[{"citation_id": "c1"}],
        traced_claims=[{"claim": "x", "citation_ids": ["c1"], "verdict": "supported"}],
        grade=[{"claim": "x", "certainty": "moderate"}],
        consensus=[{"claim": "x", "support": 3, "contrast": 1, "neutral": 0}],
        conflicting_evidence=[{"claim": "x", "contrasting_citation_ids": ["c5"]}],
        subquestions=["q1", "q2"],
        gap_fill_passes=2,
        output_profile="doctor",
        disclaimer_present=True,
    )
    assert set(payload) == {
        "pico",
        "citation_registry",
        "traced_claims",
        "grade",
        "consensus",
        "conflicting_evidence",
        "subquestions",
        "gap_fill_passes",
        "output_profile",
        "disclaimer_present",
    }
    assert payload["subquestions"] == ["q1", "q2"]
    assert payload["gap_fill_passes"] == 2
    assert payload["output_profile"] == "doctor"
    assert payload["disclaimer_present"] is True


def test_build_tier2_optional_payload_includes_falsey_but_present_values():
    # An empty list / zero / False are *produced* values and must be carried, not dropped.
    payload = tier2._build_tier2_optional_payload(
        citation_registry=[],
        gap_fill_passes=0,
        disclaimer_present=False,
    )
    assert payload["citation_registry"] == []
    assert payload["gap_fill_passes"] == 0
    assert payload["disclaimer_present"] is False
    # Unsupplied artifacts stay omitted.
    assert "traced_claims" not in payload
    assert "subquestions" not in payload


def test_build_tier2_optional_payload_only_supplied_subset():
    payload = tier2._build_tier2_optional_payload(
        subquestions=["a"], output_profile="researcher"
    )
    assert payload == {"subquestions": ["a"], "output_profile": "researcher"}


# --- Bounded iterative gap-fill retrieval (R5.1, R5.2, R5.3) ---


def test_gap_fill_disabled_never_runs():
    # Flag off => no gap-fill pass regardless of evidence shortfall (R20.2 / legacy).
    assert (
        tier2._gap_fill_should_run(
            0, enabled=False, min_results=3, max_passes=2, passes_used=0
        )
        is False
    )


def test_gap_fill_runs_only_when_evidence_below_minimum():
    # Below the minimum and budget available => permitted (R5.1).
    assert (
        tier2._gap_fill_should_run(
            1, enabled=True, min_results=3, max_passes=2, passes_used=0
        )
        is True
    )
    # At or above the minimum => not permitted (sufficient evidence).
    assert (
        tier2._gap_fill_should_run(
            3, enabled=True, min_results=3, max_passes=2, passes_used=0
        )
        is False
    )


def test_gap_fill_is_bounded_by_max_passes():
    # Budget exhausted => stop and proceed to synthesis (R5.2, R5.3).
    assert (
        tier2._gap_fill_should_run(
            0, enabled=True, min_results=3, max_passes=2, passes_used=2
        )
        is False
    )
    # A zero/negative budget never runs.
    assert (
        tier2._gap_fill_should_run(
            0, enabled=True, min_results=3, max_passes=0, passes_used=0
        )
        is False
    )


def test_gap_fill_loop_terminates_within_budget():
    # Simulate the orchestrator loop: cumulative passes can never exceed max_passes.
    max_passes = 3
    passes_used = 0
    # Evidence stays below minimum (worst case) — loop must still terminate at the bound.
    while tier2._gap_fill_should_run(
        0, enabled=True, min_results=5, max_passes=max_passes, passes_used=passes_used
    ):
        passes_used += 1
    assert passes_used == max_passes


# --- R6: Recency / trust-tier composite ranking comparator (R6.1, R6.3) ---


def _row(rid: str, *, tier=None, date=None, score=0.0, source_type=None):
    row: dict = {"id": rid, "source": "pubmed", "score": score}
    if tier is not None:
        row["trust_tier"] = tier
    if date is not None:
        row["published_at"] = date
    if source_type is not None:
        row["source_type"] = source_type
    return row


def test_rank_disabled_preserves_legacy_order():
    rows = [_row("b", tier=4), _row("a", tier=1)]
    # Flag off => identical list object/order returned (byte-for-byte legacy, R20.2).
    assert tier2._rank_sources_by_recency_trust(rows, enabled=False) is rows


def test_rank_orders_by_trust_tier_then_recency_then_score():
    rows = [
        _row("low_tier", tier=4, date="2024-01-01", score=0.9),
        _row("high_tier_old", tier=1, date="2001-01-01", score=0.1),
        _row("high_tier_new", tier=1, date="2023-01-01", score=0.1),
        _row("mid_tier", tier=2, date="2020-01-01", score=0.5),
    ]
    ranked = tier2._rank_sources_by_recency_trust(rows, enabled=True)
    assert [r["id"] for r in ranked] == [
        "high_tier_new",  # tier 1, newest
        "high_tier_old",  # tier 1, older
        "mid_tier",       # tier 2
        "low_tier",       # tier 4
    ]


def test_rank_higher_authority_sorts_first_for_same_claim():
    # R6.3: between two sources, the higher trust_tier (lower number) leads.
    rows = [_row("tier3", tier=3), _row("tier1", tier=1)]
    ranked = tier2._rank_sources_by_recency_trust(rows, enabled=True)
    assert [r["id"] for r in ranked] == ["tier1", "tier3"]


def test_rank_recency_breaks_ties_within_tier():
    rows = [
        _row("older", tier=2, date="2010-05-01"),
        _row("newer", tier=2, date="2022-05-01"),
    ]
    ranked = tier2._rank_sources_by_recency_trust(rows, enabled=True)
    assert [r["id"] for r in ranked] == ["newer", "older"]


def test_rank_unknown_signals_sort_after_known():
    rows = [_row("unknown"), _row("known", tier=1, date="2020-01-01")]
    ranked = tier2._rank_sources_by_recency_trust(rows, enabled=True)
    assert [r["id"] for r in ranked] == ["known", "unknown"]


def test_rank_is_stable_for_full_ties():
    # Identical composite keys keep original relative order (deterministic / monotonic).
    rows = [_row("first", tier=2, date="2020-01-01", score=0.4),
            _row("second", tier=2, date="2020-01-01", score=0.4)]
    ranked = tier2._rank_sources_by_recency_trust(rows, enabled=True)
    assert [r["id"] for r in ranked] == ["first", "second"]


def test_rank_key_reads_nested_metadata():
    nested = {"id": "n", "score": 0.0, "metadata": {"trust_tier": 1, "published_at": "2021-01-01"}}
    assert tier2._row_trust_tier(nested) == 1
    assert tier2._row_recency_year(nested) == 2021


# --- R6.2: trust_tier + date surfaced per citation only when ranking enabled ---


def test_build_citations_surfaces_provenance_when_rank_enabled():
    rows = [_row("s1", tier=1, date="2023-04-01", source_type="systematic_review", score=0.9)]
    citations = tier2._build_citations("topic", rows, [], rank_enabled=True)
    assert len(citations) == 1
    assert citations[0].trust_tier == 1
    assert citations[0].published_at == "2023-04-01"
    assert citations[0].source_type == "systematic_review"


def test_build_citations_omits_provenance_when_rank_disabled():
    rows = [_row("s1", tier=1, date="2023-04-01", source_type="systematic_review", score=0.9)]
    citations = tier2._build_citations("topic", rows, [], rank_enabled=False)
    assert len(citations) == 1
    # Default-off preserves the legacy citation shape (no provenance attached).
    assert citations[0].trust_tier is None
    assert citations[0].published_at is None
    assert citations[0].source_type is None


# --- R8: GRADE certainty + recommendation-strength labeling ---

_GRADE_CERTAINTY_SET = {"high", "moderate", "low", "very_low"}


def _claim_row(claim, *, status="supported", evidence_ref=None, claim_type="general"):
    return {
        "claim": claim,
        "claim_type": claim_type,
        "support_status": status,
        "evidence_ref": evidence_ref,
    }


def test_evidence_hierarchy_rank_mapping():
    # Strongest → weakest per the design Evidence-Hierarchy table.
    assert tier2._evidence_hierarchy_rank("systematic_review") == 1
    assert tier2._evidence_hierarchy_rank("meta-analysis") == 1
    assert tier2._evidence_hierarchy_rank("guideline") == 1
    assert tier2._evidence_hierarchy_rank("randomized_controlled_trial") == 2
    assert tier2._evidence_hierarchy_rank("cohort") == 3
    assert tier2._evidence_hierarchy_rank("case_series") == 4
    # Unknown / expert opinion / unranked web defaults to the weakest band.
    assert tier2._evidence_hierarchy_rank("expert_opinion") == 5
    assert tier2._evidence_hierarchy_rank(None) == 5
    assert tier2._evidence_hierarchy_rank("") == 5


def test_grade_certainty_label_in_set_and_endpoints():
    # Strongest evidence (tier 1 + systematic review) → high; weakest → very_low (R8.1, R8.2).
    assert tier2._grade_certainty_label(1, 1) == "high"
    assert tier2._grade_certainty_label(4, 5) == "very_low"
    for tier in (1, 2, 3, 4, None):
        for rank in (1, 2, 3, 4, 5):
            assert tier2._grade_certainty_label(tier, rank) in _GRADE_CERTAINTY_SET


def test_grade_certainty_monotonic_in_evidence_strength():
    # Property 13 core: a stronger trust_tier or hierarchy rank never lowers certainty.
    order = {label: i for i, label in enumerate(tier2._GRADE_CERTAINTY_ORDER)}
    # Stronger trust_tier (lower number) at fixed rank is non-decreasing in certainty.
    for rank in (1, 2, 3, 4, 5):
        levels = [order[tier2._grade_certainty_label(t, rank)] for t in (4, 3, 2, 1)]
        assert levels == sorted(levels)
    # Stronger hierarchy rank (lower number) at fixed tier is non-decreasing in certainty.
    for tier in (1, 2, 3, 4):
        levels = [order[tier2._grade_certainty_label(tier, r)] for r in (5, 4, 3, 2, 1)]
        assert levels == sorted(levels)


def test_is_recommendation_claim_detects_vi_and_en():
    assert tier2._is_recommendation_claim("Bệnh nhân nên dùng thuốc vào buổi sáng")
    assert tier2._is_recommendation_claim("Khuyến nghị theo dõi INR định kỳ")
    assert tier2._is_recommendation_claim("Patients should monitor for bleeding")
    assert tier2._is_recommendation_claim("We recommend dose reduction in CKD")
    # A plain factual claim is not a recommendation.
    assert not tier2._is_recommendation_claim("Warfarin ức chế vitamin K epoxide reductase")
    assert not tier2._is_recommendation_claim("Paracetamol is metabolized in the liver")


def test_assign_grade_labels_disabled_returns_none():
    # R8.5 / R20.2: flag off => no labels and the field is omitted downstream.
    rows = [_claim_row("a claim", evidence_ref="s1")]
    assert tier2._assign_grade_labels(rows, [], enabled=False) is None


def test_assign_grade_labels_high_certainty_from_strong_source():
    context = [_row("s1", tier=1, date="2023-01-01", source_type="systematic_review")]
    rows = [_claim_row("Treatment reduces mortality", evidence_ref="s1")]
    labels = tier2._assign_grade_labels(rows, context, enabled=True)
    assert labels == [{"claim": "Treatment reduces mortality", "certainty": "high"}]


def test_assign_grade_labels_unresolved_unsupported_claim_is_very_low():
    # A claim with no resolvable supporting source and a non-supported status → very_low.
    rows = [_claim_row("Unbacked statement", status="insufficient", evidence_ref=None)]
    labels = tier2._assign_grade_labels(rows, [], enabled=True)
    assert labels == [{"claim": "Unbacked statement", "certainty": "very_low"}]


def test_assign_grade_labels_supported_claim_falls_back_to_corpus_best():
    # evidence_ref does not resolve, but the supported claim is grounded in the corpus.
    context = [_row("s1", tier=2, date="2022-01-01", source_type="randomized_controlled_trial")]
    rows = [_claim_row("Grounded but unreferenced", status="supported", evidence_ref="missing")]
    labels = tier2._assign_grade_labels(rows, context, enabled=True)
    assert len(labels) == 1
    assert labels[0]["certainty"] in _GRADE_CERTAINTY_SET
    # tier 2 + RCT (rank 2): score 2 + 3 = 5 → moderate.
    assert labels[0]["certainty"] == "moderate"


def test_assign_grade_labels_recommendation_carries_strength():
    strong_ctx = [_row("s1", tier=1, date="2023-01-01", source_type="systematic_review")]
    rec_rows = [_claim_row("Patients should start therapy early", evidence_ref="s1")]
    labels = tier2._assign_grade_labels(rec_rows, strong_ctx, enabled=True)
    assert labels[0]["recommendation_strength"] == "strong"

    weak_ctx = [_row("s2", tier=4, source_type="expert_opinion")]
    weak_rows = [_claim_row("We recommend caution", evidence_ref="s2")]
    weak_labels = tier2._assign_grade_labels(weak_rows, weak_ctx, enabled=True)
    assert weak_labels[0]["recommendation_strength"] == "conditional"


def test_assign_grade_labels_non_recommendation_has_no_strength_key():
    context = [_row("s1", tier=1, source_type="systematic_review")]
    rows = [_claim_row("Drug X inhibits enzyme Y", evidence_ref="s1")]
    labels = tier2._assign_grade_labels(rows, context, enabled=True)
    assert "recommendation_strength" not in labels[0]


# --- R9: Evidence-agreement (Consensus) view + conflicting-evidence section -----------------


def _src(rid: str, text: str) -> dict:
    # Minimal retrieved-source row shape consumed by the consensus computation.
    return {"id": rid, "source": "pubmed", "text": text}


# A claim plus three sources engineered so the deterministic NLI core classifies one as
# supporting, one as contrasting (negation mismatch), and one as neutral (no overlap).
_CONSENSUS_CLAIM = "aspirin reduces risk"
_SUPPORT_SRC = _src("s_support", "aspirin reduces risk of stroke significantly")
_CONTRAST_SRC = _src("s_contrast", "aspirin does not reduce risk at all")
_NEUTRAL_SRC = _src("s_neutral", "completely unrelated sentence about gardening tools")


def test_compute_consensus_view_disabled_returns_none():
    # R9 flag off => both fields omitted downstream (legacy shape preserved, R20.2).
    consensus, conflicting = tier2._compute_consensus_view(
        verification_rows=[_claim_row(_CONSENSUS_CLAIM)],
        retrieved_context=[_SUPPORT_SRC, _CONTRAST_SRC, _NEUTRAL_SRC],
        enabled=False,
    )
    assert consensus is None
    assert conflicting is None


def test_compute_consensus_view_counts_partition_evaluated_sources():
    # Property 15: support + contrast + neutral == number of evaluated sources.
    sources = [_SUPPORT_SRC, _CONTRAST_SRC, _NEUTRAL_SRC]
    consensus, _ = tier2._compute_consensus_view(
        verification_rows=[_claim_row(_CONSENSUS_CLAIM)],
        retrieved_context=sources,
        enabled=True,
    )
    assert len(consensus) == 1
    entry = consensus[0]
    assert entry["claim"] == _CONSENSUS_CLAIM
    assert entry["support"] == 1
    assert entry["contrast"] == 1
    assert entry["neutral"] == 1
    assert entry["support"] + entry["contrast"] + entry["neutral"] == len(sources)


def test_compute_consensus_view_excludes_textless_sources_from_partition():
    # Sources with no usable text cannot be NLI-evaluated and are excluded from the counts.
    sources = [_SUPPORT_SRC, {"id": "blank", "text": "   "}, {"id": "missing"}]
    consensus, _ = tier2._compute_consensus_view(
        verification_rows=[_claim_row(_CONSENSUS_CLAIM)],
        retrieved_context=sources,
        enabled=True,
    )
    entry = consensus[0]
    # Only the single text-bearing source is evaluated.
    assert entry["support"] + entry["contrast"] + entry["neutral"] == 1


def test_compute_consensus_view_emits_conflicting_section_when_both_present():
    # R9.4: claim has >=1 supporting and >=1 contrasting source => section lists the contrasters.
    _, conflicting = tier2._compute_consensus_view(
        verification_rows=[_claim_row(_CONSENSUS_CLAIM)],
        retrieved_context=[_SUPPORT_SRC, _CONTRAST_SRC, _NEUTRAL_SRC],
        enabled=True,
    )
    assert conflicting == [
        {"claim": _CONSENSUS_CLAIM, "contrasting_citation_ids": ["s_contrast"]}
    ]


def test_compute_consensus_view_no_conflict_when_only_support():
    # No contrasting source => no conflicting-evidence entry (R9.4).
    _, conflicting = tier2._compute_consensus_view(
        verification_rows=[_claim_row(_CONSENSUS_CLAIM)],
        retrieved_context=[_SUPPORT_SRC, _NEUTRAL_SRC],
        enabled=True,
    )
    assert conflicting == []


# --- R11: Claim-to-study traceability + Citation Registry + provenance ----------------------


def _trace_citation(source_id: str, **kw) -> Citation:
    return Citation(
        source_id=source_id,
        source=kw.get("source", "pubmed"),
        title=kw.get("title", "A study"),
        url=kw.get("url", ""),
        relevance="high",
        study_id=kw.get("study_id"),
        source_type=kw.get("source_type"),
        trust_tier=kw.get("trust_tier"),
        published_at=kw.get("published_at"),
    )


def test_normalize_claim_verdict_mapping():
    assert tier2._normalize_claim_verdict("supported") == "supported"
    assert tier2._normalize_claim_verdict("contradicted") == "contradicted"
    assert tier2._normalize_claim_verdict("insufficient") == "unsupported"
    assert tier2._normalize_claim_verdict("unsupported") == "unsupported"
    assert tier2._normalize_claim_verdict(None) == "unsupported"


def test_derive_citation_study_id_prefers_scholarly_identifiers():
    row = {"id": "s1", "pmid": "12345678", "doi": "10.1000/xyz"}
    # PMID wins over DOI per the ordered metadata-key preference.
    assert tier2._derive_citation_study_id(_trace_citation("s1"), row) == "PMID:12345678"
    # DOI is used when no PMID is present.
    assert (
        tier2._derive_citation_study_id(_trace_citation("s1"), {"id": "s1", "doi": "10.1000/xyz"})
        == "DOI:10.1000/xyz"
    )
    # RXCUI is used for drug concepts.
    assert (
        tier2._derive_citation_study_id(_trace_citation("s1"), {"id": "s1", "rxcui": "11289"})
        == "RXCUI:11289"
    )


def test_derive_citation_study_id_falls_back_to_url_doi_then_source_id():
    # DOI embedded in the citation URL.
    citation = _trace_citation("s1", url="https://doi.org/10.1000/abc")
    assert tier2._derive_citation_study_id(citation, None) == "DOI:10.1000/abc"
    # No identifier anywhere → the retrieved source's own id (still a real source, R11.5).
    assert tier2._derive_citation_study_id(_trace_citation("s9"), None) == "s9"
    # An explicit study_id on the citation is preserved verbatim.
    assert (
        tier2._derive_citation_study_id(_trace_citation("s1", study_id="PMID:777"), {"id": "s1"})
        == "PMID:777"
    )


def test_match_citation_ids_for_claim_resolves_by_identity():
    citations = [_trace_citation("s1"), _trace_citation("s2")]
    assert tier2._match_citation_ids_for_claim("s1", citations) == ["s1"]
    # An unresolvable reference yields no citations (R11.6 suppression backbone).
    assert tier2._match_citation_ids_for_claim("nope-xyz", citations) == []
    # Empty / missing reference resolves to nothing.
    assert tier2._match_citation_ids_for_claim(None, citations) == []


def test_build_claim_trace_disabled_returns_none():
    # R11 flag off => both artifacts omitted downstream (legacy shape preserved, R20.2).
    traced, registry = tier2._build_claim_trace(
        verification_rows=[_claim_row("c", evidence_ref="s1")],
        citations=[_trace_citation("s1")],
        retrieved_context=[_row("s1", tier=1)],
        grade_labels=None,
        enabled=False,
    )
    assert traced is None
    assert registry is None


def test_build_claim_trace_registry_has_full_provenance():
    # R11.2/R11.4: every surfaced citation appears in the registry with complete provenance.
    context = [
        {
            "id": "s1",
            "source": "pubmed",
            "score": 0.9,
            "trust_tier": 1,
            "published_at": "2023-04-01",
            "source_type": "systematic_review",
            "pmid": "12345678",
        }
    ]
    traced, registry = tier2._build_claim_trace(
        verification_rows=[],
        citations=[_trace_citation("s1")],
        retrieved_context=context,
        grade_labels=None,
        enabled=True,
    )
    assert registry == [
        {
            "citation_id": "s1",
            "study_id": "PMID:12345678",
            "source_type": "systematic_review",
            "trust_tier": 1,
            "published_at": "2023-04-01",
        }
    ]
    assert traced == []


def test_build_claim_trace_links_supported_claim_with_certainty():
    # R11.1: a supported claim is linked to its specific supporting citation id(s).
    context = [{"id": "s1", "source": "pubmed", "trust_tier": 1, "source_type": "rct"}]
    rows = [_claim_row("Treatment helps", status="supported", evidence_ref="s1")]
    grade = [{"claim": "Treatment helps", "certainty": "high"}]
    traced, _ = tier2._build_claim_trace(
        verification_rows=rows,
        citations=[_trace_citation("s1")],
        retrieved_context=context,
        grade_labels=grade,
        enabled=True,
    )
    assert traced == [
        {
            "claim": "Treatment helps",
            "citation_ids": ["s1"],
            "verdict": "supported",
            "certainty": "high",
        }
    ]


def test_build_claim_trace_suppresses_unsupported_claim():
    # R11.6: a non-supported claim is suppressed even when its evidence_ref resolves.
    context = [{"id": "s1", "source": "pubmed", "trust_tier": 1}]
    rows = [_claim_row("Unbacked", status="insufficient", evidence_ref="s1")]
    traced, _ = tier2._build_claim_trace(
        verification_rows=rows,
        citations=[_trace_citation("s1")],
        retrieved_context=context,
        grade_labels=None,
        enabled=True,
    )
    assert traced == []


def test_build_claim_trace_suppresses_supported_claim_without_resolvable_citation():
    # R11.6: a supported claim with no resolvable supporting citation is suppressed (never
    # gets a fabricated citation).
    context = [{"id": "s1", "source": "pubmed", "trust_tier": 1}]
    rows = [_claim_row("Floating claim", status="supported", evidence_ref="unmatched-xyz")]
    traced, _ = tier2._build_claim_trace(
        verification_rows=rows,
        citations=[_trace_citation("s1")],
        retrieved_context=context,
        grade_labels=None,
        enabled=True,
    )
    assert traced == []


def test_build_claim_trace_default_trust_tier_and_source_type_when_unknown():
    # The registry's trust_tier/source_type fields are always present (R11.2); an unknown
    # source falls back to the lowest authority band and an "unknown" source type.
    context = [{"id": "s1", "source": "web"}]
    traced, registry = tier2._build_claim_trace(
        verification_rows=[],
        citations=[_trace_citation("s1")],
        retrieved_context=context,
        grade_labels=None,
        enabled=True,
    )
    assert registry[0]["trust_tier"] == tier2._DEFAULT_CITATION_TRUST_TIER
    assert registry[0]["source_type"] == "unknown"
    # No scholarly identifier and no DOI URL → fall back to the retrieved source id.
    assert registry[0]["study_id"] == "s1"


def test_build_claim_trace_registry_is_superset_of_traced_citation_ids():
    # Property 24 backbone: every traced/anchored citation id resolves into the registry.
    context = [
        {"id": "s1", "source": "pubmed", "trust_tier": 1},
        {"id": "s2", "source": "pubmed", "trust_tier": 2},
    ]
    rows = [_claim_row("Supported claim", status="supported", evidence_ref="s1")]
    traced, registry = tier2._build_claim_trace(
        verification_rows=rows,
        citations=[_trace_citation("s1"), _trace_citation("s2")],
        retrieved_context=context,
        grade_labels=None,
        enabled=True,
    )
    registry_ids = {entry["citation_id"] for entry in registry}
    assert {"s1", "s2"} <= registry_ids
    for traced_claim in traced:
        for citation_id in traced_claim["citation_ids"]:
            assert citation_id in registry_ids
