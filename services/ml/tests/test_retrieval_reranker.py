import time

import pytest

from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.reranker import NeuralReranker


@pytest.fixture(autouse=True)
def _clear_neural_reranker_cache() -> None:
    NeuralReranker.clear_cache()
    yield
    NeuralReranker.clear_cache()


def test_reranker_disabled_returns_passthrough_and_metadata_fields() -> None:
    docs = [
        Document(id="doc-1", text="warfarin guide", metadata={"score": 0.2, "source": "pubmed"}),
        Document(id="doc-2", text="ibuprofen warning", metadata={"score": 0.3, "source": "openfda"}),
    ]

    reranker = NeuralReranker(enabled=False, top_n=2, timeout_ms=120)
    result = reranker.rerank("warfarin ibuprofen", docs, top_k=1)

    assert [doc.id for doc in result.documents] == ["doc-1"]
    assert result.metadata["rerank_enabled"] is False
    assert result.metadata["rerank_topn"] == 0
    assert isinstance(result.metadata["rerank_latency_ms"], float)
    assert result.metadata["rerank_latency_ms"] >= 0.0
    assert result.metadata["rerank_cache_hit"] is False


def test_reranker_enabled_applies_topn_and_sets_doc_fields() -> None:
    docs = [
        Document(
            id="doc-low-overlap",
            text="General medication reminder without target terms.",
            metadata={"score": 0.1, "source": "pubmed"},
        ),
        Document(
            id="doc-high-overlap",
            text="Warfarin ibuprofen interaction with bleeding risk evidence.",
            metadata={"score": 0.05, "source": "openfda"},
        ),
        Document(
            id="doc-outside-topn",
            text="Daily blood pressure check advice.",
            metadata={"score": 99.0, "source": "internal"},
        ),
    ]

    reranker = NeuralReranker(enabled=True, top_n=2, timeout_ms=200)
    result = reranker.rerank("warfarin ibuprofen bleeding", docs)

    assert [doc.id for doc in result.documents[:2]] == ["doc-high-overlap", "doc-low-overlap"]
    assert result.documents[0].metadata["rerank_rank"] == 1
    assert result.documents[1].metadata["rerank_rank"] == 2
    assert isinstance(result.documents[0].metadata["rerank_score"], float)
    assert result.documents[2].metadata["rerank_applied"] is False

    assert result.metadata["rerank_topn"] == 2
    assert isinstance(result.metadata["rerank_latency_ms"], float)
    assert result.metadata["rerank_applied_count"] == 2
    assert result.metadata["rerank_cache_hit"] is False


def test_reranker_embedding_cosine_scoring_reorders_candidates() -> None:
    class _DeterministicEmbedder:
        def embed_batch(self, texts):
            assert len(texts) == 3
            return [
                [1.0, 0.0],  # query
                [1.0, 0.0],  # doc-1 aligned
                [0.0, 1.0],  # doc-2 orthogonal
            ]

    docs = [
        Document(id="doc-1", text="alpha", metadata={"score": 0.0, "source": "internal"}),
        Document(id="doc-2", text="beta", metadata={"score": 0.0, "source": "internal"}),
    ]
    reranker = NeuralReranker(
        enabled=True,
        top_n=2,
        timeout_ms=200,
        embedder=_DeterministicEmbedder(),
    )

    result = reranker.rerank("query", docs)

    assert [doc.id for doc in result.documents[:2]] == ["doc-1", "doc-2"]
    assert result.metadata["rerank_reason"] == "ok"
    assert result.metadata["rerank_applied_count"] == 2


def test_reranker_embedding_error_uses_safe_fallback() -> None:
    class _FailingEmbedder:
        def embed_batch(self, texts):  # noqa: ARG002
            raise RuntimeError("embedding_unavailable")

    docs = [
        Document(id="doc-1", text="warfarin", metadata={"source": "pubmed", "score": 0.8}),
        Document(id="doc-2", text="ibuprofen", metadata={"source": "openfda", "score": 0.7}),
    ]
    reranker = NeuralReranker(enabled=True, top_n=2, timeout_ms=200, embedder=_FailingEmbedder())

    result = reranker.rerank("warfarin ibuprofen", docs, top_k=2)

    assert [doc.id for doc in result.documents] == ["doc-1", "doc-2"]
    assert result.metadata["rerank_reason"] == "error_fallback"
    assert result.metadata["rerank_applied_count"] == 0
    assert result.metadata["rerank_topn"] == 0


def test_reranker_handles_non_positive_top_k() -> None:
    reranker = NeuralReranker(enabled=True, top_n=5)
    result = reranker.rerank(
        "query",
        [Document(id="doc", text="text", metadata={"source": "internal"})],
        top_k=0,
    )

    assert result.documents == []
    assert result.metadata["rerank_topn"] == 0
    assert result.metadata["rerank_reason"] == "top_k_non_positive"
    assert isinstance(result.metadata["rerank_latency_ms"], float)
    assert result.metadata["rerank_cache_hit"] is False


def test_reranker_clamps_topn_to_candidate_count() -> None:
    reranker = NeuralReranker(enabled=True, top_n=10)
    docs = [
        Document(id="doc-1", text="warfarin", metadata={"source": "pubmed"}),
        Document(id="doc-2", text="ibuprofen", metadata={"source": "openfda"}),
    ]

    result = reranker.rerank("warfarin ibuprofen", docs)

    assert result.metadata["rerank_topn"] == 2
    assert result.metadata["rerank_applied_count"] == 2
    assert isinstance(result.metadata["rerank_latency_ms"], float)
    assert result.metadata["rerank_cache_hit"] is False


def test_reranker_timeout_fallback_does_not_break_retrieval(monkeypatch) -> None:
    def _slow_placeholder(cls, query: str, doc: Document) -> float:  # noqa: ARG001
        time.sleep(0.004)
        return 0.1

    monkeypatch.setattr(NeuralReranker, "_placeholder_score", classmethod(_slow_placeholder))
    reranker = NeuralReranker(enabled=True, top_n=2, timeout_ms=1)
    docs = [
        Document(id="doc-1", text="warfarin", metadata={"source": "pubmed", "score": 0.8}),
        Document(id="doc-2", text="ibuprofen", metadata={"source": "openfda", "score": 0.7}),
    ]

    result = reranker.rerank("warfarin ibuprofen", docs, top_k=2)

    assert [doc.id for doc in result.documents] == ["doc-1", "doc-2"]
    assert result.metadata["rerank_reason"] == "timeout_fallback"
    assert result.metadata["rerank_timed_out"] is True
    assert result.metadata["rerank_applied_count"] == 0
    assert result.metadata["rerank_topn"] == 0
    assert result.metadata["rerank_cache_hit"] is False


def test_reranker_uses_cached_result_for_identical_inputs(monkeypatch) -> None:
    docs = [
        Document(
            id="doc-1",
            text="Warfarin and ibuprofen increase bleeding risk in older adults.",
            metadata={"source": "openfda", "score": 0.9},
        ),
        Document(
            id="doc-2",
            text="General medication reminder.",
            metadata={"source": "internal", "score": 0.2},
        ),
    ]
    reranker = NeuralReranker(
        enabled=True,
        top_n=2,
        timeout_ms=200,
        cache_enabled=True,
        cache_ttl_seconds=120,
        cache_max_entries=64,
    )

    first = reranker.rerank("warfarin ibuprofen bleeding risk", docs, top_k=2)
    assert first.metadata["rerank_cache_hit"] is False

    def _should_not_run(cls, query: str, doc: Document) -> float:  # noqa: ARG001
        raise AssertionError("placeholder scorer should not be called on cache hit")

    monkeypatch.setattr(NeuralReranker, "_placeholder_score", classmethod(_should_not_run))

    second = reranker.rerank("warfarin ibuprofen bleeding risk", docs, top_k=2)

    assert [doc.id for doc in first.documents] == [doc.id for doc in second.documents]
    assert second.metadata["rerank_cache_hit"] is True
    assert second.metadata["rerank_reason"] == "cache_hit"
    assert isinstance(second.metadata["rerank_cache_age_ms"], float)
    assert second.metadata["rerank_cache_age_ms"] >= 0.0


def test_reranker_llm_hybrid_uses_llm_scores_to_reorder() -> None:
    class _DeterministicEmbedder:
        def embed_batch(self, texts):
            assert len(texts) == 3
            return [
                [1.0, 0.0],  # query
                [0.9, 0.1],  # doc-1
                [0.9, 0.1],  # doc-2
            ]

    class _FakeLlmClient:
        def generate(self, prompt: str, system_prompt: str | None = None):  # noqa: ARG002
            class _Response:
                content = (
                    '{"scores":[{"doc_id":"doc-1","score":0.10},'
                    '{"doc_id":"doc-2","score":0.98}]}'
                )
                model = "fake-llm"

            return _Response()

    docs = [
        Document(id="doc-1", text="first", metadata={"source": "internal", "score": 0.1}),
        Document(id="doc-2", text="second", metadata={"source": "internal", "score": 0.1}),
    ]
    reranker = NeuralReranker(
        enabled=True,
        strategy="llm_hybrid",
        llm_enabled=True,
        llm_client=_FakeLlmClient(),
        top_n=2,
        timeout_ms=200,
        embedder=_DeterministicEmbedder(),
    )

    result = reranker.rerank("query", docs)
    assert [doc.id for doc in result.documents[:2]] == ["doc-2", "doc-1"]
    assert result.metadata["rerank_llm_used"] is True
    assert (
        result.documents[0].metadata["rerank_llm_score"]
        > result.documents[1].metadata["rerank_llm_score"]
    )


def test_reranker_llm_hybrid_falls_back_when_llm_fails() -> None:
    class _DeterministicEmbedder:
        def embed_batch(self, texts):
            assert len(texts) == 3
            return [
                [1.0, 0.0],  # query
                [1.0, 0.0],  # doc-1
                [0.0, 1.0],  # doc-2
            ]

    class _BrokenLlmClient:
        def generate(self, prompt: str, system_prompt: str | None = None):  # noqa: ARG002
            raise RuntimeError("llm_down")

    docs = [
        Document(id="doc-1", text="alpha", metadata={"source": "internal", "score": 0.0}),
        Document(id="doc-2", text="beta", metadata={"source": "internal", "score": 0.0}),
    ]
    reranker = NeuralReranker(
        enabled=True,
        strategy="llm_hybrid",
        llm_enabled=True,
        llm_client=_BrokenLlmClient(),
        top_n=2,
        timeout_ms=200,
        embedder=_DeterministicEmbedder(),
    )

    result = reranker.rerank("query", docs)
    assert [doc.id for doc in result.documents[:2]] == ["doc-1", "doc-2"]
    assert result.metadata["rerank_llm_used"] is False
    assert isinstance(result.metadata.get("rerank_llm_error"), str)
