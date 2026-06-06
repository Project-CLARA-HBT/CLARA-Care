"""Property-based test for query-only embedding in the online hybrid retriever.

Feature: rag-knowledge-pipeline, Property 12: Query-only embedding.

Design reference (design.md -> Correctness Properties):
    Property 12: Query-only embedding. For any online retrieval call, exactly
    one embedding request is issued (the query); no document is embedded at
    query time.

Requirements (requirements.md -> Requirement 7, Acceptance Criteria):
    7.1 WHEN an online retrieval call is made, THE Hybrid_Retriever SHALL issue
        exactly one embedding request, embedding only the query, and SHALL embed
        no document at query time.

Target: :class:`clara_ml.rag.store.hybrid_retriever.HybridRetriever`. The online
retriever is the *query side* of the offline/online embedding split: the offline
ingestion plane embeds documents once and persists their vectors, so at query
time the retriever must embed ONLY the query (exactly one ``embed_query`` call)
and never re-embed any candidate document.

Test doubles (no DB / no network):

* ``CountingEmbedder`` -- records every embedding call. ``embed_query`` bumps a
  query counter and returns a deterministic vector; the document-embedding entry
  points (``embed_batch`` / ``embed_documents`` / ``__call__``) bump a *separate*
  document counter so any accidental document re-embedding by the retriever is
  detectable. The retriever's own embedder must show exactly one query call and
  zero document calls.
* ``FakeSparseIndex`` -- returns a pre-built ``RankedChunk`` list for the sparse
  arm without touching any embedder, DB, or network.
* a dense-search seam (``dense_search=...``) -- returns a pre-built
  ``RankedChunk`` list for the dense arm, again without embedding anything.
* ``FakeReranker`` -- returns the fused candidates in order (optionally trimmed
  to ``top_k``) and never calls the retriever's embedder. (The production
  reranker owns its *own* embedder; it never embeds through the retriever's.)

The property drives >= 100 Hypothesis examples varying the query string and the
dense / sparse candidate counts, asserting on every call that the retriever
embedded the query exactly once and embedded zero documents.

Validates: Requirements 7.1
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# Import the store package first so it initializes before the retriever module
# is pulled in: ``clara_ml.rag.store`` -> hybrid_retriever -> score_engine ->
# embedder form an import cycle that only resolves cleanly when the store
# package loads first. Doing so here keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.store.hybrid_retriever import HybridRetriever, RetrievalFilters
from clara_ml.rag.store.sparse_index import RankedChunk

# Property tests run >= 100 iterations; the deadline is disabled because the
# in-process fusion/rerank loop timing is environment-dependent and not what we
# assert on.
_PBT_SETTINGS = settings(max_examples=200, deadline=None)


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #
class CountingEmbedder:
    """Embedder double that counts query vs document embedding calls.

    Only :meth:`embed_query` is a legitimate online call. The document-embedding
    entry points all increment a *separate* counter so the property can prove the
    retriever never re-embeds documents at query time.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim
        self.query_calls = 0
        self.doc_calls = 0
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        self.queries.append(text)
        digest = hashlib.sha256(str(text).encode("utf-8", "ignore")).digest()
        return [digest[i] / 255.0 for i in range(self.dim)]

    # --- document-embedding entry points (must never be hit by retrieve) ---
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        self.doc_calls += 1
        return [[0.0] * self.dim for _ in texts]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.doc_calls += 1
        return [[0.0] * self.dim for _ in texts]

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        self.doc_calls += 1
        return [[0.0] * self.dim for _ in texts]


class FakeSparseIndex:
    """Sparse arm double: returns a fixed candidate list, embeds nothing."""

    def __init__(self, chunks: list[RankedChunk]) -> None:
        self._chunks = chunks
        self.calls = 0

    def search(
        self,
        query_text: str,  # noqa: ARG002 - candidates are fixed, query is irrelevant here
        *,
        top_k: int,
        lang: str | None = None,  # noqa: ARG002 - unused by the double
        filters: Any | None = None,  # noqa: ARG002 - unused by the double
    ) -> list[RankedChunk]:
        self.calls += 1
        return list(self._chunks[: max(0, int(top_k))])


@dataclass
class _FakeRerankResult:
    documents: list[Document]


class FakeReranker:
    """Reranker double: returns fused docs (trimmed) without embedding anything."""

    def __init__(self) -> None:
        self.calls = 0

    def rerank(
        self,
        query: str,  # noqa: ARG002 - ordering is pass-through for this double
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> _FakeRerankResult:
        self.calls += 1
        docs = list(documents)
        if top_k is not None:
            docs = docs[: max(0, int(top_k))]
        return _FakeRerankResult(documents=docs)


def _make_dense_search(chunks: list[RankedChunk]):
    """Build a dense-search seam that returns fixed candidates, embedding nothing.

    The retriever passes ``(q_vec, n, filters)``; the double ignores the vector
    (it was produced by the single ``embed_query`` call) and returns the
    pre-built candidate slice.
    """

    def _dense_search(
        q_vec: Sequence[float],  # noqa: ARG001 - vector ignored; candidates are fixed
        n: int,
        filters: RetrievalFilters | None,  # noqa: ARG001 - unused by the double
    ) -> list[RankedChunk]:
        return list(chunks[: max(0, int(n))])

    return _dense_search


# --------------------------------------------------------------------------- #
# Generators
# --------------------------------------------------------------------------- #
@st.composite
def _ranked_chunks(draw: st.DrawFn, *, retriever: str) -> list[RankedChunk]:
    """Generate a (possibly empty) candidate list with unique chunk ids."""
    ids = draw(
        st.lists(st.integers(min_value=1, max_value=1000), min_size=0, max_size=8, unique=True)
    )
    chunks: list[RankedChunk] = []
    for cid in ids:
        score = draw(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
        )
        trust_tier = draw(st.sampled_from([1, 2, 3, 4, None]))
        chunks.append(
            RankedChunk(
                chunk_id=cid,
                score=score,
                retriever=retriever,
                document_id=cid,
                section_path=f"sec/{cid}",
                section_type="body",
                lang="en",
                trust_tier=trust_tier,
                text=f"chunk-{cid}",
                meta={"source": "unit-test", "effective_date": "2024-01-01"},
            )
        )
    return chunks


# Non-empty, non-whitespace queries so an embedding call is always made (the
# retriever short-circuits before embedding on an empty/whitespace query). The
# default ``st.text`` alphabet is utf-8 safe (no surrogates).
_queries = st.text(min_size=1, max_size=48).filter(lambda s: s.strip())


def _build_retriever(
    *,
    embedder: CountingEmbedder,
    dense: list[RankedChunk],
    sparse: list[RankedChunk],
    candidate_n: int,
) -> tuple[HybridRetriever, FakeReranker, FakeSparseIndex]:
    reranker = FakeReranker()
    sparse_index = FakeSparseIndex(sparse)
    retriever = HybridRetriever(
        embedder=embedder,
        sparse_index=sparse_index,
        reranker=reranker,
        dense_search=_make_dense_search(dense),
        query_expander=None,
        candidate_n=candidate_n,
        trust_tier_ranking=False,
    )
    return retriever, reranker, sparse_index


# --------------------------------------------------------------------------- #
# Property 12: Query-only embedding
# --------------------------------------------------------------------------- #
@given(
    query=_queries,
    dense=_ranked_chunks(retriever="dense"),
    sparse=_ranked_chunks(retriever="bm25"),
    top_k=st.integers(min_value=1, max_value=20),
    candidate_n=st.integers(min_value=1, max_value=50),
)
@_PBT_SETTINGS
def test_retrieve_embeds_only_the_query_exactly_once(
    query: str,
    dense: list[RankedChunk],
    sparse: list[RankedChunk],
    top_k: int,
    candidate_n: int,
) -> None:
    """For any query + candidate set, retrieve embeds the query exactly once.

    Validates: Requirements 7.1
    """
    embedder = CountingEmbedder()
    retriever, _reranker, _sparse_index = _build_retriever(
        embedder=embedder, dense=dense, sparse=sparse, candidate_n=candidate_n
    )

    retriever.retrieve(query, top_k=top_k)

    # Exactly one embedding request, and it embedded ONLY the query.
    assert embedder.query_calls == 1
    assert embedder.doc_calls == 0
    assert embedder.queries == [query]


@given(
    query=_queries,
    dense=_ranked_chunks(retriever="dense"),
    sparse=_ranked_chunks(retriever="bm25"),
)
@_PBT_SETTINGS
def test_retrieve_with_filters_still_embeds_query_once(
    query: str,
    dense: list[RankedChunk],
    sparse: list[RankedChunk],
) -> None:
    """Applying retrieval filters never adds or removes the single embed call.

    Validates: Requirements 7.1
    """
    embedder = CountingEmbedder()
    retriever, _reranker, _sparse_index = _build_retriever(
        embedder=embedder, dense=dense, sparse=sparse, candidate_n=25
    )
    filters = RetrievalFilters(trust_tier_max=2, lang="vi", section_type="body")

    retriever.retrieve(query, top_k=5, filters=filters)

    assert embedder.query_calls == 1
    assert embedder.doc_calls == 0
    assert embedder.queries == [query]


# --------------------------------------------------------------------------- #
# Example / edge-case unit tests reinforcing the same contract
# --------------------------------------------------------------------------- #
def test_single_retrieve_makes_exactly_one_query_embedding() -> None:
    embedder = CountingEmbedder()
    dense = [RankedChunk(chunk_id=1, score=0.9, retriever="dense", text="a")]
    sparse = [RankedChunk(chunk_id=2, score=0.8, retriever="bm25", text="b")]
    retriever, reranker, sparse_index = _build_retriever(
        embedder=embedder, dense=dense, sparse=sparse, candidate_n=10
    )

    docs = retriever.retrieve("aspirin contraindications", top_k=3)

    assert embedder.query_calls == 1
    assert embedder.doc_calls == 0
    assert sparse_index.calls == 1
    assert reranker.calls == 1
    # No fabrication: returned ids are a subset of the candidate union.
    candidate_ids = {"1", "2"}
    assert {d.id for d in docs} <= candidate_ids


def test_empty_query_makes_no_embedding_call() -> None:
    embedder = CountingEmbedder()
    retriever, _reranker, _sparse_index = _build_retriever(
        embedder=embedder,
        dense=[RankedChunk(chunk_id=1, score=0.5, retriever="dense", text="a")],
        sparse=[],
        candidate_n=10,
    )

    assert retriever.retrieve("   ", top_k=5) == []
    assert embedder.query_calls == 0
    assert embedder.doc_calls == 0


def test_non_positive_top_k_makes_no_embedding_call() -> None:
    embedder = CountingEmbedder()
    retriever, _reranker, _sparse_index = _build_retriever(
        embedder=embedder,
        dense=[RankedChunk(chunk_id=1, score=0.5, retriever="dense", text="a")],
        sparse=[],
        candidate_n=10,
    )

    assert retriever.retrieve("aspirin", top_k=0) == []
    assert embedder.query_calls == 0
    assert embedder.doc_calls == 0
