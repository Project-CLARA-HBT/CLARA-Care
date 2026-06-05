"""Tests for NCBI E-utilities API-key wiring in the PubMed source-hub fetcher.

A configured ``NCBI_API_KEY`` must be attached to PubMed requests (raising the
per-IP rate limit from 3 to 10 req/s); when unset, requests stay anonymous and
no ``api_key`` param is sent.
"""

from clara_api.api.v1.endpoints import research


def test_ncbi_params_omit_key_when_unset(monkeypatch) -> None:
    monkeypatch.setattr(research._research_settings, "ncbi_api_key", "")
    params = research._ncbi_eutils_params({"db": "pubmed", "term": "aspirin"})
    assert "api_key" not in params
    assert params == {"db": "pubmed", "term": "aspirin"}


def test_ncbi_params_attach_key_when_set(monkeypatch) -> None:
    monkeypatch.setattr(research._research_settings, "ncbi_api_key", "  test-key-123  ")
    params = research._ncbi_eutils_params({"db": "pubmed", "term": "aspirin"})
    assert params["api_key"] == "test-key-123"
    # Original params preserved, input dict not mutated.
    assert params["db"] == "pubmed"
    assert params["term"] == "aspirin"


def test_ncbi_params_does_not_mutate_input(monkeypatch) -> None:
    monkeypatch.setattr(research._research_settings, "ncbi_api_key", "k")
    original = {"db": "pubmed", "id": "1,2,3"}
    research._ncbi_eutils_params(original)
    assert "api_key" not in original
