from clara_ml.lifemap.entity_resolution import (
    DenseCandidate,
    TerminologyEntry,
    normalize_vietnamese,
    resolve_entity,
)

TERMS = (
    TerminologyEntry(
        code="R51",
        display="Đau đầu",
        aliases=("nhức đầu",),
        system="ICD-10",
        mapping_revision="vn-map-2026-07",
    ),
    TerminologyEntry(
        code="G43",
        display="Đau nửa đầu",
        aliases=("migraine",),
        system="ICD-10",
        mapping_revision="vn-map-2026-07",
    ),
)


def test_vietnamese_normalization_and_alias_are_revisioned() -> None:
    assert normalize_vietnamese("  NHỨC   ĐẦU ") == "nhuc dau"
    result = resolve_entity("nhức đầu", terminology=TERMS)
    assert result.status == "resolved"
    assert result.candidates[0].code == "R51"
    assert result.candidates[0].source == "alias"
    assert result.candidates[0].mapping_revision == "vn-map-2026-07"
    assert result.auto_confirmable is False


def test_graph_filter_precedes_dense_reranking() -> None:
    result = resolve_entity(
        "đau",
        terminology=TERMS,
        dense_candidates=(
            DenseCandidate("R51", 0.9),
            DenseCandidate("G43", 0.99),
        ),
        graph_allowed_codes=frozenset({"R51"}),
        rerank_scores={"G43": 1.0, "R51": 0.1, "not-a-candidate": 1.0},
    )
    assert [candidate.code for candidate in result.candidates] == ["R51"]


def test_close_candidates_are_ambiguous_not_silently_resolved() -> None:
    result = resolve_entity(
        "đau",
        terminology=TERMS,
        dense_candidates=(
            DenseCandidate("R51", 0.90),
            DenseCandidate("G43", 0.89),
        ),
    )
    assert result.status == "ambiguous"
    assert result.as_dict()["auto_confirmable"] is False


def test_unknown_code_and_inactive_entries_cannot_enter_candidates() -> None:
    result = resolve_entity(
        "unknown",
        terminology=TERMS,
        dense_candidates=(DenseCandidate("NOT-GOVERNED", 1.0),),
    )
    assert result.status == "unmapped"
    assert result.candidates == ()
