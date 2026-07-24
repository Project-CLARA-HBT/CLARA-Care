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


def test_scientific_gateway_respects_provider_query_overrides(monkeypatch) -> None:
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
        provider_query_overrides={"pubmed": "warfarin ibuprofen randomized trial bleeding"},
    )

    assert captured.get("pubmed_query") == "warfarin ibuprofen randomized trial bleeding"
    assert telemetry.get("provider_query_overrides") == {
        "pubmed": "warfarin ibuprofen randomized trial bleeding"
    }


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


def test_retrieve_pubmed_hydrates_dapa_ckd_abstract_and_identifiers(monkeypatch) -> None:
    gateway = ExternalSourceGateway()
    calls: list[str] = []

    def _fake_fetch_json(url, timeout_seconds, headers=None):  # type: ignore[no-untyped-def]
        calls.append(url)
        if "esearch.fcgi" in url:
            # A duplicate upstream id must not create duplicate evidence rows.
            return {"esearchresult": {"idlist": ["32970396", "32970396"]}}
        if "esummary.fcgi" in url:
            return {
                "result": {
                    "32970396": {
                        "title": "Dapagliflozin in Patients with Chronic Kidney Disease",
                        "fulljournalname": "The New England Journal of Medicine",
                        "pubdate": "2020 Oct 8",
                        "pubtype": ["Journal Article", "Randomized Controlled Trial"],
                    }
                }
            }
        raise AssertionError(f"unexpected JSON URL: {url}")

    dapa_efetch = """<?xml version="1.0"?>
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>32970396</PMID>
          <Article>
            <ArticleTitle>Dapagliflozin in Patients with Chronic Kidney Disease</ArticleTitle>
            <Abstract>
              <AbstractText Label="RESULTS">The primary outcome occurred in 9.2% of the dapagliflozin group and 14.5% of the placebo group.</AbstractText>
              <AbstractText Label="CONCLUSIONS">The risk of a sustained decline in kidney function was significantly lower with dapagliflozin.</AbstractText>
            </Abstract>
            <PublicationTypeList>
              <PublicationType>Journal Article</PublicationType>
              <PublicationType>Randomized Controlled Trial</PublicationType>
            </PublicationTypeList>
          </Article>
          <DataBankList>
            <DataBank>
              <DataBankName>ClinicalTrials.gov</DataBankName>
              <AccessionNumberList>
                <AccessionNumber>NCT03036150</AccessionNumber>
              </AccessionNumberList>
            </DataBank>
          </DataBankList>
        </MedlineCitation>
        <PubmedData>
          <ArticleIdList>
            <ArticleId IdType="pubmed">32970396</ArticleId>
            <ArticleId IdType="doi">10.1056/NEJMoa2024816</ArticleId>
          </ArticleIdList>
        </PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """

    def _fake_fetch_text(url, timeout_seconds, headers=None):  # type: ignore[no-untyped-def]
        calls.append(url)
        assert "efetch.fcgi" in url
        assert "32970396" in url
        assert timeout_seconds == 12.0
        return dapa_efetch

    monkeypatch.setattr(ExternalSourceGateway, "_fetch_json", staticmethod(_fake_fetch_json))
    monkeypatch.setattr(ExternalSourceGateway, "_fetch_text", staticmethod(_fake_fetch_text))

    docs = gateway.retrieve_pubmed(
        '("DAPA-CKD"[Title/Abstract] OR "EMPA-KIDNEY"[Title/Abstract])',
        top_k=10,
        timeout_seconds=2.0,
    )

    assert len(docs) == 1
    document = docs[0]
    assert document.id == "pubmed-32970396"
    assert "primary outcome occurred in 9.2%" in document.text
    assert "sustained decline in kidney function" in document.text
    assert document.metadata["pmid"] == "32970396"
    assert document.metadata["doi"] == "10.1056/NEJMoa2024816"
    assert document.metadata["nct_ids"] == ["NCT03036150"]
    assert document.metadata["publication_types"] == [
        "Journal Article",
        "Randomized Controlled Trial",
    ]
    assert document.metadata["source_type"] == "primary_trial"
    assert document.metadata["study_design"] == "randomized_controlled_trial"
    assert sum("efetch.fcgi" in url for url in calls) == 1


def test_retrieve_pubmed_keeps_summary_when_optional_efetch_fails(monkeypatch) -> None:
    gateway = ExternalSourceGateway()

    def _fake_fetch_json(url, timeout_seconds, headers=None):  # type: ignore[no-untyped-def]
        if "esearch.fcgi" in url:
            return {"esearchresult": {"idlist": ["32970396"]}}
        return {
            "result": {
                "32970396": {
                    "title": "Dapagliflozin in Patients with Chronic Kidney Disease",
                    "source": "N Engl J Med",
                    "pubdate": "2020",
                    "pubtype": ["Randomized Controlled Trial"],
                }
            }
        }

    def _failed_fetch_text(url, timeout_seconds, headers=None):  # type: ignore[no-untyped-def]
        raise TimeoutError("efetch unavailable")

    monkeypatch.setattr(ExternalSourceGateway, "_fetch_json", staticmethod(_fake_fetch_json))
    monkeypatch.setattr(ExternalSourceGateway, "_fetch_text", staticmethod(_failed_fetch_text))

    docs = gateway.retrieve_pubmed("DAPA-CKD", top_k=3, timeout_seconds=1.0)

    assert len(docs) == 1
    assert docs[0].metadata["pmid"] == "32970396"
    assert docs[0].metadata["publication_types"] == ["Randomized Controlled Trial"]
    assert docs[0].metadata["source_type"] == "primary_trial"
    assert docs[0].metadata["doi"] == ""
    assert docs[0].metadata["nct_ids"] == []


def test_retrieve_europe_pmc_keeps_empa_kidney_abstract_metadata_and_dedupes(
    monkeypatch,
) -> None:
    gateway = ExternalSourceGateway()
    empa_result = {
        "source": "MED",
        "id": "36331190",
        "pmid": "36331190",
        "pmcid": "PMC7614055",
        "doi": "10.1056/NEJMoa2204233",
        "title": "Empagliflozin in Patients with Chronic Kidney Disease",
        "journalTitle": "The New England Journal of Medicine",
        "pubYear": "2023",
        "abstractText": (
            "Progression of kidney disease or death from cardiovascular causes "
            "occurred in 13.1% of the empagliflozin group and 16.9% of the placebo group."
        ),
        "pubTypeList": {
            "pubType": ["Journal Article", "Randomized Controlled Trial"]
        },
        "clinicalTrialNumber": "NCT03594110",
    }

    def _fake_fetch_json(url, timeout_seconds, headers=None):  # type: ignore[no-untyped-def]
        assert "resultType=core" in url
        return {"resultList": {"result": [empa_result, dict(empa_result)]}}

    monkeypatch.setattr(ExternalSourceGateway, "_fetch_json", staticmethod(_fake_fetch_json))

    docs = gateway.retrieve_europe_pmc(
        '(TITLE_ABS:"DAPA-CKD" OR TITLE_ABS:"EMPA-KIDNEY")',
        top_k=10,
        timeout_seconds=2.0,
    )

    assert len(docs) == 1
    document = docs[0]
    assert document.id == "europepmc-med-36331190"
    assert "13.1% of the empagliflozin group" in document.text
    assert "16.9% of the placebo group" in document.text
    assert document.metadata["pmid"] == "36331190"
    assert document.metadata["pmcid"] == "PMC7614055"
    assert document.metadata["doi"] == "10.1056/NEJMoa2204233"
    assert document.metadata["nct_ids"] == ["NCT03594110"]
    assert document.metadata["publication_types"] == [
        "Journal Article",
        "Randomized Controlled Trial",
    ]
    assert document.metadata["source_type"] == "primary_trial"
    assert document.metadata["study_design"] == "randomized_controlled_trial"
