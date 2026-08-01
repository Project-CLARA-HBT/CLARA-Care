"""Contracts for safe persistent convergence from live scientific gap-fill.

These tests are network/DB-free.  They lock the conversion boundary so a
request-time document cannot become a corpus write unless it has a curated
source key, HTTPS provenance, and non-empty source material.  The downstream
atomic ingestion path is already covered by the ingestion property suite.
"""

from __future__ import annotations

from clara_ml.ingestion.live_gap_fill import documents_to_records
from clara_ml.rag.retrieval.domain import Document


def test_live_gap_fill_accepts_only_curated_https_provenance() -> None:
    records = documents_to_records(
        [
            Document(
                id="pubmed-123",
                text="A source abstract.",
                metadata={
                    "source": "pubmed",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                    "title": "A source title",
                },
            ),
            Document(
                id="untrusted-web",
                text="Must never be persisted.",
                metadata={"source": "searxng", "url": "https://example.test/article"},
            ),
            Document(
                id="insecure-pubmed",
                text="Must never be persisted.",
                metadata={"source": "pubmed", "url": "http://pubmed.ncbi.nlm.nih.gov/456/"},
            ),
        ]
    )

    assert set(records) == {"pubmed"}
    record = records["pubmed"][0]
    assert record.external_id == "pubmed-123"
    assert record.source_key == "pubmed"
    assert record.url.startswith("https://")
    # Authority is intentionally re-resolved from the source registry by the
    # orchestrator; live metadata cannot confer an authority tier.
    assert record.trust_tier == 4


def test_live_gap_fill_does_not_need_or_retain_the_triggering_query() -> None:
    records = documents_to_records(
        [
            Document(
                id="europepmc-med-1",
                text="Published source material only.",
                metadata={
                    "source": "europepmc",
                    "url": "https://europepmc.org/article/MED/1",
                },
            )
        ]
    )

    record = records["europepmc"][0]
    assert record.external_id == "europepmc-med-1"
    assert record.raw_text == "Published source material only."
