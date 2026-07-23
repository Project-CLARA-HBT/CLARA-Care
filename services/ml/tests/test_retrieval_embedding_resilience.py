from __future__ import annotations

from typing import Any

import pytest

from clara_ml.config import settings
from clara_ml.rag.embedder import EmbeddingUnavailableError
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.in_memory import InMemoryRetriever
from clara_ml.rag.retrieval.source_router import decide_source_route


class _Embedding503:
    def embed_batch(self, _texts: list[str]) -> list[list[float]]:
        raise EmbeddingUnavailableError("HTTP 503")


def test_external_documents_survive_embedding_503_with_degraded_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = InMemoryRetriever([], embedder=_Embedding503())  # type: ignore[arg-type]
    fetched = [
        Document(
            id="pm-1",
            text="DAPA-CKD showed kidney outcome benefit in chronic kidney disease.",
            metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/1"},
        ),
        Document(
            id="epmc-1",
            text="EMPA-KIDNEY included people with chronic kidney disease without diabetes.",
            metadata={"source": "europepmc", "url": "https://europepmc.org/article/1"},
        ),
    ]

    def _fetch(**kwargs: Any) -> list[Document]:
        telemetry = kwargs["telemetry"]
        telemetry.update(
            {
                "provider_events": [
                    {
                        "provider": "pubmed",
                        "source": "pubmed",
                        "status": "completed",
                        "documents": 1,
                    },
                    {
                        "provider": "europepmc",
                        "source": "europepmc",
                        "status": "completed",
                        "documents": 1,
                    },
                ]
            }
        )
        return fetched

    monkeypatch.setattr(
        retriever.external_gateway,
        "retrieve_scientific_with_telemetry",
        _fetch,
    )

    docs = retriever.retrieve_external_scientific(
        "Compare DAPA-CKD and EMPA-KIDNEY",
        top_k=2,
    )

    assert {doc.id for doc in docs} == {"pm-1", "epmc-1"}
    assert all(doc.metadata.get("ranking_degraded") is True for doc in docs)
    assert retriever.last_trace["source_errors"]["embedding"] == [
        "EmbeddingUnavailableError"
    ]
    assert retriever.last_trace["index_phase"]["ranking_fallback"] == (
        "deterministic_lexical"
    )
    assert retriever.last_trace["source_attempts"][0]["status"] == "completed"


def test_embedding_503_fallback_ignores_stale_scores_and_marks_only_top_k() -> None:
    retriever = InMemoryRetriever([], embedder=_Embedding503())  # type: ignore[arg-type]
    stale = Document(
        id="persistent-stale",
        text="Mediterranean diet patterns in population health.",
        metadata={"source": "pubmed", "score": 0.9},
    )
    relevant = Document(
        id="europepmc-live",
        text=(
            "DAPA-CKD and EMPA-KIDNEY evidence for SGLT2 inhibitors "
            "in chronic kidney disease."
        ),
        metadata={"source": "europepmc", "score": 0.0},
    )

    ranked, trace = retriever._index_candidates(
        query="Compare DAPA-CKD and EMPA-KIDNEY SGLT2 kidney evidence",
        candidates=[stale, relevant],
        top_k=1,
        rag_sources=None,
    )

    assert [doc.id for doc in ranked] == ["europepmc-live"]
    rows_by_id = {row["doc_id"]: row for row in trace["score_trace"]}
    assert rows_by_id["europepmc-live"]["selected"] is True
    assert rows_by_id["persistent-stale"]["selected"] is False
    assert rows_by_id["persistent-stale"]["final_score"] < 0.9
    assert sum(bool(row["selected"]) for row in trace["score_trace"]) == 1


class _EmptyPersistentRetriever:
    def retrieve(self, *_args: Any, **_kwargs: Any) -> list[Document]:
        return []


def test_underfilled_persistent_web_request_falls_through_to_full_hybrid() -> None:
    pipe = RagPipelineP1(
        retriever=InMemoryRetriever([], embedder=_Embedding503()),  # type: ignore[arg-type]
        deepseek_api_key="",
        hybrid_retriever=_EmptyPersistentRetriever(),
    )

    result = pipe._persistent_retrieve(
        "SGLT2 chronic kidney disease",
        top_k=5,
        rag_sources=[],
        scientific_query="DAPA-CKD EMPA-KIDNEY",
        scientific_provider_query_overrides=None,
        rag_reranker_enabled=True,
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=True,
    )

    assert result is None


class _FastRescueRetriever:
    def __init__(self) -> None:
        self.last_trace: dict[str, Any] = {}
        self.hybrid_calls: list[dict[str, Any]] = []

    def retrieve_internal(self, *_args: Any, **_kwargs: Any) -> list[Document]:
        self.last_trace = {
            "mode": "internal",
            "search_phase": {
                "query_terms": [],
                "connectors_attempted": [
                    {
                        "provider": "internal_corpus",
                        "status": "completed",
                        "documents": 0,
                    }
                ],
                "source_errors": {},
                "total_candidates": 0,
            },
            "index_phase": {"selected_count": 0},
            "source_attempts": [],
            "source_errors": {},
        }
        return []

    def retrieve(self, query: str, **kwargs: Any) -> list[Document]:
        self.hybrid_calls.append({"query": query, **kwargs})
        docs = [
            Document(
                id="pubmed-rescue-1",
                text="SGLT2 inhibitor evidence in chronic kidney disease.",
                metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/1"},
            )
        ]
        attempts = [
            {
                "provider": "pubmed",
                "status": "completed",
                "documents": 1,
            },
            {
                "source": "searxng-search",
                "status": "completed",
                "documents": 1,
            },
        ]
        self.last_trace = {
            "mode": "hybrid",
            "search_phase": {
                "query_terms": ["sglt2", "kidney"],
                "connectors_attempted": attempts,
                "source_errors": {},
                "total_candidates": 1,
            },
            "index_phase": {"selected_count": 1},
            "source_attempts": attempts,
            "source_errors": {},
            "index_summary": {"selected_count": 1},
            "top_documents": [],
        }
        return docs


def test_fast_zero_internal_results_get_one_bounded_external_rescue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = _FastRescueRetriever()
    pipe = RagPipelineP1(
        retriever=retriever,  # type: ignore[arg-type]
        deepseek_api_key="",
    )
    monkeypatch.setattr(pipe, "_persistent_retrieval_active", lambda: False)
    monkeypatch.setattr(settings, "rag_external_connectors_enabled", True)
    monkeypatch.setattr(settings, "rag_graphrag_enabled", False)
    monkeypatch.setattr(settings, "rag_biomed_graph_enabled", False)

    result = pipe.run(
        "Current evidence for SGLT2 inhibitors in chronic kidney disease",
        planner_hints={
            "research_mode": "fast",
            "scientific_retrieval_enabled": False,
            "web_retrieval_enabled": False,
            "file_retrieval_enabled": True,
        },
    )

    assert result.retrieved_ids == ["pubmed-rescue-1"]
    assert len(retriever.hybrid_calls) == 1
    call = retriever.hybrid_calls[0]
    assert call["top_k"] <= 3
    assert call["scientific_retrieval_enabled"] is True
    assert call["web_retrieval_enabled"] is True
    assert {
        item["id"] for item in call["rag_sources"] if isinstance(item, dict)
    } == {"pubmed", "europepmc", "searxng"}
    trace = result.context_debug["retrieval_trace"]
    assert trace["zero_context_fast_rescue"]["attempted"] is True
    assert trace["stack_coverage"]["scientific_used"] is True
    assert trace["stack_coverage"]["web_used"] is True


def test_both_enabled_route_reports_scientific_priority() -> None:
    decision = decide_source_route(
        query="Compare DAPA-CKD and EMPA-KIDNEY",
        research_mode="deep",
        has_uploaded_documents=False,
        is_ddi_query=False,
        is_ddi_critical_query=False,
        language_hint="en",
        web_policy_allowed=True,
    )

    assert decision.retrieval_route == "scientific-heavy"
    assert "multi_source_scientific_priority" in decision.reason_codes
    assert decision.enable_scientific is True
    assert decision.enable_web is True
