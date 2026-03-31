from clara_ml.rag.retrieval.external_gateway import ExternalSourceGateway


def test_scientific_gateway_includes_provider_query_in_telemetry(monkeypatch) -> None:
    gateway = ExternalSourceGateway()
    captured: dict[str, str] = {}

    def _fake_pubmed(self, query: str, *, top_k: int, timeout_seconds: float):  # type: ignore[no-untyped-def]
        captured["pubmed_query"] = query
        return []

    monkeypatch.setattr(ExternalSourceGateway, "retrieve_pubmed", _fake_pubmed)

    telemetry: dict[str, object] = {}
    gateway.retrieve_scientific_with_telemetry(
        "Tương tác Warfarin với thuốc giảm đau phổ biến",
        top_k=3,
        timeout_seconds=1.0,
        telemetry=telemetry,
        allowed_providers={"pubmed"},
    )

    assert "pubmed_query" in captured
    assert "warfarin" in captured["pubmed_query"].lower()
    provider_events = telemetry.get("provider_events")
    assert isinstance(provider_events, list)
    assert provider_events
    assert isinstance(provider_events[0], dict)
    assert provider_events[0].get("query")


def test_scientific_gateway_rewrites_semantic_query_for_ddi(monkeypatch) -> None:
    gateway = ExternalSourceGateway()
    captured: dict[str, str] = {}

    def _fake_semantic(self, query: str, *, top_k: int, timeout_seconds: float):  # type: ignore[no-untyped-def]
        captured["semantic_query"] = query
        return []

    monkeypatch.setattr(ExternalSourceGateway, "retrieve_semantic_scholar", _fake_semantic)

    telemetry: dict[str, object] = {}
    gateway.retrieve_scientific_with_telemetry(
        "Tương tác Warfarin với thuốc giảm đau phổ biến",
        top_k=3,
        timeout_seconds=1.0,
        telemetry=telemetry,
        allowed_providers={"semantic_scholar"},
    )

    query_used = captured.get("semantic_query", "").lower()
    assert "warfarin" in query_used
    assert any(token in query_used for token in ["interaction", "bleeding", "inr"])


def test_retrieve_rxnorm_parses_candidate_rows(monkeypatch) -> None:
    gateway = ExternalSourceGateway()

    def _fake_fetch_json(url, timeout_seconds, headers=None):  # type: ignore[no-untyped-def]
        assert "approximateTerm.json" in url
        return {
            "approximateGroup": {
                "candidate": [
                    {"rxcui": "11289", "name": "warfarin", "score": "98", "rank": "1"},
                    {"rxcui": "5640", "name": "ibuprofen", "score": "95", "rank": "2"},
                ]
            }
        }

    monkeypatch.setattr(
        ExternalSourceGateway,
        "_fetch_json",
        staticmethod(_fake_fetch_json),
    )

    docs = gateway.retrieve_rxnorm(
        "Tương tác warfarin với ibuprofen",
        top_k=3,
        timeout_seconds=2.0,
    )
    assert len(docs) >= 2
    assert docs[0].id.startswith("rxnorm-")
    assert docs[0].metadata.get("source") == "rxnorm"
    assert "RxCUI" in docs[0].text
