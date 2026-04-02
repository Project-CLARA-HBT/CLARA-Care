from contextlib import contextmanager

from clara_ml.config import settings
from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.score_engine import DocumentScorer


class _StubEmbedder:
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Deterministic vectors for unit tests; ranking relies mainly on lexical/policy logic.
        return [[1.0, 0.0] for _ in texts]


@contextmanager
def _biomedical_rerank_flags(*, enabled: bool, alpha: float = 0.28, top_n: int = 8):
    previous_enabled = settings.rag_biomedical_rerank_enabled
    previous_alpha = settings.rag_biomedical_rerank_alpha
    previous_top_n = settings.rag_biomedical_rerank_top_n
    settings.rag_biomedical_rerank_enabled = enabled
    settings.rag_biomedical_rerank_alpha = alpha
    settings.rag_biomedical_rerank_top_n = top_n
    try:
        yield
    finally:
        settings.rag_biomedical_rerank_enabled = previous_enabled
        settings.rag_biomedical_rerank_alpha = previous_alpha
        settings.rag_biomedical_rerank_top_n = previous_top_n


def test_score_engine_filters_ddi_irrelevant_documents() -> None:
    scorer = DocumentScorer(embedder=_StubEmbedder())
    query = "Tương tác warfarin với ibuprofen"

    docs = [
        Document(
            id="pubmed-warfarin-diet",
            text="Warfarin diet management and nutrition counseling for stable INR.",
            metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/1/"},
        ),
        Document(
            id="openfda-warfarin-label",
            text="Warfarin sodium labeling information and major safety warnings.",
            metadata={"source": "openfda", "url": "https://open.fda.gov/apis/drug/label/"},
        ),
        Document(
            id="pubmed-warfarin-ibuprofen-ddi",
            text=(
                "Warfarin and ibuprofen interaction increases bleeding risk. "
                "Clinical monitoring of INR is recommended."
            ),
            metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/2/"},
        ),
    ]

    ranked = scorer.score_documents(query, docs, top_k=5)
    ranked_ids = [item.id for item in ranked]

    assert "pubmed-warfarin-diet" not in ranked_ids
    assert "openfda-warfarin-label" in ranked_ids
    assert "pubmed-warfarin-ibuprofen-ddi" in ranked_ids


def test_score_engine_recognizes_primary_alias_coumadin() -> None:
    scorer = DocumentScorer(embedder=_StubEmbedder())
    query = "Tuong tac warfarin va aspirin"
    docs = [
        Document(
            id="dailymed-coumadin-aspirin",
            text="Coumadin and aspirin interaction can increase bleeding risk.",
            metadata={"source": "dailymed", "url": "https://dailymed.nlm.nih.gov/"},
        ),
        Document(
            id="pubmed-unrelated",
            text="Mediterranean diet outcomes in primary prevention.",
            metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/3/"},
        ),
    ]

    ranked = scorer.score_documents(query, docs, top_k=2)
    ranked_ids = [item.id for item in ranked]

    assert "dailymed-coumadin-aspirin" in ranked_ids
    assert "pubmed-unrelated" not in ranked_ids


def test_score_engine_applies_hard_filter_for_ddi_critical_query() -> None:
    scorer = DocumentScorer(embedder=_StubEmbedder())
    query = "Critical DDI warfarin with ibuprofen major bleeding risk"
    docs = [
        Document(
            id="openfda-warfarin-label",
            text="Warfarin sodium label with boxed warning and safety notes.",
            metadata={"source": "openfda", "url": "https://open.fda.gov/apis/drug/label/"},
        ),
        Document(
            id="pubmed-warfarin-ibuprofen-bleeding",
            text=(
                "Warfarin and ibuprofen interaction significantly increases bleeding risk. "
                "Major hemorrhage events reported in observational data."
            ),
            metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/4/"},
        ),
    ]

    ranked = scorer.score_documents(query, docs, top_k=3)
    ranked_ids = [item.id for item in ranked]

    assert "pubmed-warfarin-ibuprofen-bleeding" in ranked_ids
    assert "openfda-warfarin-label" not in ranked_ids


def test_score_engine_emits_rrf_breakdown_for_selected_documents() -> None:
    scorer = DocumentScorer(embedder=_StubEmbedder())
    query = "warfarin ibuprofen interaction bleeding risk"
    docs = [
        Document(
            id="doc-a",
            text="Warfarin ibuprofen interaction and bleeding risk evidence summary.",
            metadata={"source": "pubmed"},
        ),
        Document(
            id="doc-b",
            text="Warfarin monitoring information with INR reminders.",
            metadata={"source": "dailymed"},
        ),
    ]
    score_trace: list[dict] = []

    ranked = scorer.score_documents(query, docs, top_k=2, score_trace=score_trace)

    assert ranked
    assert all("rrf_score" in (item.metadata or {}) for item in ranked)
    selected_rows = [row for row in score_trace if row.get("excluded") is False]
    assert selected_rows
    assert all("rrf_score" in row and "pre_rrf_score" in row for row in selected_rows)


def test_score_engine_biomedical_rerank_boosts_score_when_enabled() -> None:
    scorer = DocumentScorer(embedder=_StubEmbedder())
    query = "warfarin ibuprofen interaction major bleeding risk"
    docs = [
        Document(
            id="doc-signal-strong",
            text=(
                "Warfarin with ibuprofen has major contraindication and bleeding risk. "
                "Label warning and INR monitoring are required."
            ),
            metadata={"source": "openfda"},
        ),
        Document(
            id="doc-signal-weaker",
            text="Warfarin and ibuprofen co-use requires attention in routine follow-up.",
            metadata={"source": "pubmed"},
        ),
    ]

    with _biomedical_rerank_flags(enabled=False, alpha=0.4, top_n=2):
        ranked_without_rerank = scorer.score_documents(query, docs, top_k=2)
    with _biomedical_rerank_flags(enabled=True, alpha=0.4, top_n=2):
        ranked_with_rerank = scorer.score_documents(query, docs, top_k=2)

    without_score = float((ranked_without_rerank[0].metadata or {}).get("score") or 0.0)
    with_score = float((ranked_with_rerank[0].metadata or {}).get("score") or 0.0)
    breakdown = (ranked_with_rerank[0].metadata or {}).get("score_breakdown", {})

    assert with_score > without_score
    assert breakdown.get("biomedical_rerank_enabled") is True
    assert float(breakdown.get("biomedical_rerank_signal") or 0.0) > 0.0
    assert (
        float((ranked_with_rerank[0].metadata or {}).get("biomedical_rerank_factor") or 1.0) > 1.0
    )


def test_score_engine_biomedical_rerank_respects_top_n_limit() -> None:
    scorer = DocumentScorer(embedder=_StubEmbedder())
    query = "warfarin ibuprofen interaction bleeding"
    docs = [
        Document(
            id="doc-1",
            text="Warfarin and ibuprofen interaction with bleeding risk and contraindication.",
            metadata={"source": "openfda"},
        ),
        Document(
            id="doc-2",
            text="Warfarin and ibuprofen interaction notes.",
            metadata={"source": "pubmed"},
        ),
    ]

    with _biomedical_rerank_flags(enabled=True, alpha=0.35, top_n=1):
        ranked = scorer.score_documents(query, docs, top_k=2)

    first = ranked[0].metadata or {}
    second = ranked[1].metadata or {}
    assert first.get("biomedical_rerank_enabled") is True
    assert second.get("biomedical_rerank_enabled") is False
