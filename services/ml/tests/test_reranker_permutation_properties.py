"""Property-based tests for cross-encoder reranker permutation + timeout-safety.

Feature: rag-knowledge-pipeline, Property 16: Reranker permutation and
timeout-safety.

Design reference (design.md -> Correctness Properties):
    Property 16: Reranker permutation and timeout-safety. Reranker output is
    always a permutation of its input prefix; on timeout/error it returns the
    original order (never empties or fabricates results).

Requirements (requirements.md -> Requirement 8, Acceptance Criteria):
    8.1 WHEN reranking, THE Cross_Encoder_Reranker SHALL output a permutation of
        its input prefix, inventing no document and dropping no document, with
        any remainder appended in original order.
    8.2 IF the reranker exceeds ``RAG_RERANKER_TIMEOUT_MS`` or raises an error,
        THEN THE Cross_Encoder_Reranker SHALL return the original input order.

Target: :class:`clara_ml.rag.retrieval.reranker.NeuralReranker` with
``strategy='cross_encoder'`` and an INJECTED ``cross_encoder_scorer`` so no
network call happens. The injected scorer maps ``doc_id -> relevance`` (a plain
in-memory dict), letting us drive the rerank ordering deterministically while
covering three sub-properties:

* PERMUTATION -- the multiset of output document ids equals the multiset of
  input ids (no doc invented, none dropped); the remainder beyond ``top_n`` is
  appended preserving its original order.
* TIMEOUT / ERROR SAFETY -- when the injected scorer raises, or when the model
  is unavailable (scorer returns ``{}`` / ``None``), the reranker returns the
  ORIGINAL input order unchanged (still a permutation).
* DETERMINISM -- the same ``(query, docs, strategy, scorer)`` yields the same
  output order across repeated and independent invocations.

Each reranker is constructed with ``cache_enabled=False`` so the shared class
cache never carries results between generated examples.

Validates: Requirements 8.1, 8.2.
"""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

# Import the store package first so it fully initializes before reranker is
# pulled in. reranker -> embedder -> store.schema and store/__init__ ->
# hybrid_retriever -> score_engine -> embedder form an import cycle that only
# resolves cleanly when ``clara_ml.rag.store`` loads first; doing so here keeps
# this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.reranker import NeuralReranker

# Property tests run >= 100 iterations; deadline disabled because timing of the
# in-process scoring loop is environment-dependent and not what we assert on.
_PBT_SETTINGS = settings(max_examples=150, deadline=None)


@pytest.fixture(autouse=True)
def _clear_neural_reranker_cache():
    """Isolate the shared class-level rerank cache from any cross-talk."""
    NeuralReranker.clear_cache()
    yield
    NeuralReranker.clear_cache()


# --------------------------------------------------------------------------- #
# Generators
# --------------------------------------------------------------------------- #
@st.composite
def _documents(draw: st.DrawFn) -> list[Document]:
    """Generate a non-empty list of Documents with UNIQUE ids.

    Ids are built from a unique integer pool so no document is accidentally
    deduplicated; text/metadata are incidental to the permutation contract but
    are varied to keep generated cases realistic.
    """
    suffixes = draw(
        st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=8, unique=True)
    )
    docs: list[Document] = []
    for suffix in suffixes:
        text = draw(st.text(min_size=0, max_size=40))
        source = draw(st.sampled_from(["pubmed", "openfda", "dailymed", "internal", ""]))
        score = draw(
            st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False)
        )
        docs.append(
            Document(id=f"doc-{suffix}", text=text, metadata={"source": source, "score": score})
        )
    return docs


@st.composite
def _docs_scoremap_topn(draw: st.DrawFn) -> tuple[list[Document], dict[str, float], int]:
    """Generate documents, a (possibly partial) scorer mapping, and a ``top_n``.

    The mapping intentionally covers only a random subset of ids: missing
    per-doc scores must still keep the output a permutation (no doc dropped).
    ``top_n`` is drawn independently of the document count so cases where
    ``top_n < len(docs)`` exercise the "remainder appended in original order"
    branch, and ``top_n >= len(docs)`` exercise the full-pool branch.
    """
    docs = draw(_documents())
    score_map: dict[str, float] = {}
    for doc in docs:
        if draw(st.booleans()):
            score_map[doc.id] = draw(
                st.floats(
                    min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False
                )
            )
    top_n = draw(st.integers(min_value=1, max_value=12))
    return docs, score_map, top_n


def _make_scorer(score_map: Mapping[str, float]):
    """Build an injected cross-encoder scorer backed by an in-memory mapping.

    Returns relevance only for the requested documents that are present in the
    mapping (mirrors a real scorer that may not score every candidate). No
    network access.
    """

    def _scorer(query: str, documents: Sequence[Document]) -> Mapping[str, float]:  # noqa: ARG001
        return {doc.id: score_map[doc.id] for doc in documents if doc.id in score_map}

    return _scorer


def _build_reranker(scorer, *, top_n: int) -> NeuralReranker:
    return NeuralReranker(
        enabled=True,
        strategy="cross_encoder",
        cross_encoder_scorer=scorer,
        cache_enabled=False,
        top_n=top_n,
        timeout_ms=5_000,
    )


# --------------------------------------------------------------------------- #
# Property 16a: permutation + remainder ordering
# --------------------------------------------------------------------------- #
@_PBT_SETTINGS
@given(data=_docs_scoremap_topn(), query=st.text(min_size=0, max_size=20))
def test_reranker_output_is_permutation_with_remainder_preserved(
    data: tuple[list[Document], dict[str, float], int],
    query: str,
) -> None:
    """Output is a permutation of the input; remainder beyond top_n kept in order.

    Validates: Requirements 8.1, 8.2 (Property 16).
    """
    docs, score_map, top_n = data
    reranker = _build_reranker(_make_scorer(score_map), top_n=top_n)

    result = reranker.rerank(query, docs)  # top_k=None -> nothing truncated

    input_ids = [doc.id for doc in docs]
    output_ids = [doc.id for doc in result.documents]

    # No document invented and none dropped.
    assert Counter(output_ids) == Counter(input_ids)

    # The remainder beyond the rerank pool is appended preserving original order.
    rerank_topn = min(reranker.top_n, len(docs))
    assert output_ids[rerank_topn:] == input_ids[rerank_topn:]


# --------------------------------------------------------------------------- #
# Property 16b: timeout / error safety
# --------------------------------------------------------------------------- #
@_PBT_SETTINGS
@given(docs=_documents(), query=st.text(min_size=0, max_size=20))
def test_reranker_returns_original_order_when_scorer_raises(
    docs: list[Document],
    query: str,
) -> None:
    """A raising scorer falls back to the original input order (still a permutation).

    Validates: Requirements 8.2 (Property 16).
    """

    def _raising_scorer(q: str, documents: Sequence[Document]):  # noqa: ARG001
        raise RuntimeError("cross_encoder_boom")

    reranker = _build_reranker(_raising_scorer, top_n=5)

    result = reranker.rerank(query, docs)

    output_ids = [doc.id for doc in result.documents]
    input_ids = [doc.id for doc in docs]
    assert output_ids == input_ids
    assert result.metadata["rerank_reason"] == "error_fallback"
    assert result.metadata["rerank_applied_count"] == 0


@_PBT_SETTINGS
@given(
    docs=_documents(),
    query=st.text(min_size=0, max_size=20),
    return_none=st.booleans(),
)
def test_reranker_returns_original_order_when_model_unavailable(
    docs: list[Document],
    query: str,
    return_none: bool,
) -> None:
    """An unavailable model (scorer returns {} / None) preserves the original order.

    Validates: Requirements 8.2 (Property 16).
    """

    def _unavailable_scorer(q: str, documents: Sequence[Document]):  # noqa: ARG001
        return None if return_none else {}

    reranker = _build_reranker(_unavailable_scorer, top_n=5)

    result = reranker.rerank(query, docs)

    output_ids = [doc.id for doc in result.documents]
    input_ids = [doc.id for doc in docs]
    assert output_ids == input_ids
    assert result.metadata["rerank_reason"] == "error_fallback"
    assert result.metadata["rerank_applied_count"] == 0


# --------------------------------------------------------------------------- #
# Property 16c: determinism
# --------------------------------------------------------------------------- #
@_PBT_SETTINGS
@given(data=_docs_scoremap_topn(), query=st.text(min_size=0, max_size=20))
def test_reranker_is_deterministic_for_same_inputs(
    data: tuple[list[Document], dict[str, float], int],
    query: str,
) -> None:
    """Same (query, docs, strategy, scorer) => identical output order.

    Exercised both for repeated calls on one instance and for an independent
    instance built with the same scorer mapping.

    Validates: Requirements 8.1 (Property 16).
    """
    docs, score_map, top_n = data

    reranker_a = _build_reranker(_make_scorer(score_map), top_n=top_n)
    first = [doc.id for doc in reranker_a.rerank(query, docs).documents]
    second = [doc.id for doc in reranker_a.rerank(query, docs).documents]
    assert first == second

    reranker_b = _build_reranker(_make_scorer(dict(score_map)), top_n=top_n)
    third = [doc.id for doc in reranker_b.rerank(query, docs).documents]
    assert first == third
