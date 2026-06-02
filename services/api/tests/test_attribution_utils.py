from clara_api.core.attribution import build_attribution, normalize_source_used


def test_normalize_source_used_splits_delimited_string() -> None:
    values = normalize_source_used("rxnav, openfda;pubmed\nclinicaltrials")
    assert values == ["rxnav", "openfda", "pubmed", "clinicaltrials"]


def test_build_attribution_does_not_inflate_source_used_when_missing() -> None:
    attribution = build_attribution(
        channel="chat",
        mode="evidence_rag",
        sources=[
            {"id": "pubmed", "name": "PubMed"},
            {"id": "openfda", "name": "openFDA"},
        ],
        citations_payload=[],
        source_used=[],
        source_errors={},
    )
    assert attribution["source_used"] == []
    assert attribution["source_count"] == 2
