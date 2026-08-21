"""Property-based tests for BM25 ranking sanity.

Feature: rag-knowledge-pipeline, Property 15: BM25 ranking sanity.

Design reference (design.md -> Correctness Properties):
    Property 15: BM25 ranking sanity. For a query term ``q`` and two chunks
    where chunk A contains ``q`` with higher TF and the corpus IDF favors
    ``q``, A's BM25/FTS rank is at least as high as a chunk B not containing
    ``q`` (real IDF/TF-saturation/length-norm behavior, unlike naive overlap).

Requirement 7.5 (requirements.md -> Requirement 7, Acceptance Criteria #5):
    WHEN a query term with favorable corpus IDF appears with higher term
    frequency in chunk A than in chunk B that lacks the term, THE Sparse_Index
    SHALL rank chunk A at least as high as chunk B.

Target: the pure, DB-free ranking helpers exported by
:mod:`clara_ml.rag.store.sparse_index`:

* :func:`term_frequency` -- counts whole-token occurrences of a query term in a
  chunk's text using the *same* tokenizer the FTS layer indexes with. This is
  the quantity behind "more occurrences / better coverage of the query terms".
* :func:`bm25_sanity_holds` -- expresses the Property 15 ordering invariant as
  ``score_with_term >= score_without_term``.
* :func:`build_tsquery_terms` -- the sanitizer; used here to confirm each
  generated query term survives tokenization unchanged so ``term_frequency``
  counts what the index would index.

The real ranking happens in Postgres via ``ts_rank_cd`` (no DB available in a
unit test). Property 15 is validated *without a DB* by:

1. deriving each document's query-term frequency with the real
   :func:`term_frequency` helper, then
2. mapping those frequencies through a faithful BM25 surrogate that is
   monotonically non-decreasing in term frequency for the **all-else-equal**
   case (documents of equal length, so length-normalization is constant and a
   favorable, strictly-positive IDF), and
3. asserting the real :func:`bm25_sanity_holds` confirms the resulting order.

The BM25 surrogate uses the standard Okapi BM25 term weight
``idf * tf*(k1+1) / (tf + k1*(1-b + b*dl/avgdl))``. With ``dl == avgdl`` (equal
document length) and a fixed positive ``idf`` it is zero at ``tf == 0`` and
strictly increasing in ``tf`` -- exactly the TF-saturation / length-norm
behavior ``ts_rank_cd`` exhibits when all else is equal. This isolates the TF
monotonicity Property 15 asserts, instead of re-implementing the index.

Three complementary properties are exercised:

* SINGLE-TERM MONOTONICITY -- two equal-length docs; the one with the higher
  term frequency of ``q`` ranks at least as high (and vice versa).
* ZERO-TERM NON-OUTRANKING -- a doc containing none of the query terms never
  outranks an equal-length doc that contains the term.
* MULTI-TERM COVERAGE -- a doc covering a superset of the query terms with at
  least as many occurrences of each ranks at least as high than one covering
  fewer (the "better coverage" clause).

Validates: Requirements 7.5.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

# Import the store package first so it fully initializes before sparse_index is
# pulled in as a top-level import; store/__init__ -> hybrid_retriever -> ...
# forms an import cycle that only resolves cleanly when ``clara_ml.rag.store``
# loads first. Doing so here keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from clara_ml.rag.store.sparse_index import (
    bm25_sanity_holds,
    build_tsquery_terms,
    term_frequency,
)

# ---------------------------------------------------------------------------
# Faithful, monotone BM25 surrogate (test-side model of ts_rank_cd behavior)
# ---------------------------------------------------------------------------

# Favorable, strictly-positive IDF: Property 15 stipulates "the corpus IDF
# favors q". A constant positive value is sufficient and keeps the surrogate's
# only varying input the term frequency (all else equal).
_FAVORABLE_IDF = 1.0
_K1 = 1.2
_B = 0.75


def _bm25_term_weight(tf: int, idf: float, doc_len: int, avg_len: float) -> float:
    """Okapi BM25 weight for one term: 0 at tf<=0, monotone increasing in tf.

    For ``doc_len == avg_len`` (equal-length documents) the denominator reduces
    to ``tf + k1`` so the weight is strictly increasing in ``tf`` and zero when
    the term is absent -- the all-else-equal TF-saturation behavior Property 15
    relies on.
    """

    if tf <= 0:
        return 0.0
    denom = tf + _K1 * (1.0 - _B + _B * (doc_len / avg_len))
    return idf * tf * (_K1 + 1.0) / denom


def _bm25_score(
    term_freqs: dict[str, int], doc_len: int, avg_len: float, idf: float = _FAVORABLE_IDF
) -> float:
    """Sum the per-term BM25 weights for a (single- or multi-term) query."""

    return sum(_bm25_term_weight(tf, idf, doc_len, avg_len) for tf in term_freqs.values())


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

# Lowercase ASCII tokens survive build_tsquery_terms verbatim, so term_frequency
# counts exactly what the FTS layer would index.
_term = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=8)


def _assemble(tokens: list[str], draw: st.DrawFn) -> str:
    """Shuffle ``tokens`` (deterministically, via Hypothesis) into a text blob."""

    shuffled = list(draw(st.permutations(tokens)))
    return " ".join(shuffled)


def _term_occurrences(term: str, count: int, draw: st.DrawFn) -> list[str]:
    """Return ``count`` case-varied occurrences of ``term``.

    Mixing upper/lower/title case exercises the case-insensitive counting in
    ``term_frequency`` while keeping the true occurrence count exactly ``count``.
    """

    return [draw(st.sampled_from([term, term.upper(), term.capitalize()])) for _ in range(count)]


@st.composite
def _equal_length_single_term(
    draw: st.DrawFn,
) -> tuple[str, int, int, int, str, str]:
    """Two equal-length docs differing only in the term frequency of ``q``.

    Filler tokens are ``q + "x"`` -- guaranteed distinct from ``q`` -- so the
    only query-term signal is the controlled number of ``q`` occurrences and
    both docs have identical token length (all else equal).
    """

    q = draw(_term)
    n = draw(st.integers(min_value=1, max_value=20))
    tf_a = draw(st.integers(min_value=0, max_value=n))
    tf_b = draw(st.integers(min_value=0, max_value=n))
    filler = q + "x"

    doc_a = _assemble(_term_occurrences(q, tf_a, draw) + [filler] * (n - tf_a), draw)
    doc_b = _assemble(_term_occurrences(q, tf_b, draw) + [filler] * (n - tf_b), draw)
    return q, tf_a, tf_b, n, doc_a, doc_b


@st.composite
def _zero_term_vs_present(
    draw: st.DrawFn,
) -> tuple[str, int, int, str, str]:
    """An equal-length pair: doc A contains ``q`` (tf>=1), doc B contains none."""

    q = draw(_term)
    n = draw(st.integers(min_value=1, max_value=20))
    tf_a = draw(st.integers(min_value=1, max_value=n))
    filler = q + "x"

    doc_with = _assemble(_term_occurrences(q, tf_a, draw) + [filler] * (n - tf_a), draw)
    doc_without = _assemble([filler] * n, draw)
    return q, tf_a, n, doc_with, doc_without


@st.composite
def _coverage_multi_term(
    draw: st.DrawFn,
) -> tuple[list[str], dict[str, int], dict[str, int], int, str, str]:
    """Equal-length docs where doc A covers a superset of query terms.

    For every query term, ``tf_a[t] >= tf_b[t]`` (doc A has at least as many
    occurrences / at least as much coverage). Both docs are padded with a
    filler token longer than every query term (so it can equal none of them) up
    to a shared length ``n``.
    """

    terms = draw(st.lists(_term, min_size=1, max_size=4, unique=True))
    tf_b = {t: draw(st.integers(min_value=0, max_value=6)) for t in terms}
    tf_a = {t: tf_b[t] + draw(st.integers(min_value=0, max_value=6)) for t in terms}

    sum_a = sum(tf_a.values())
    n = max(sum_a + draw(st.integers(min_value=0, max_value=6)), 1)
    filler = "z" * (max(len(t) for t in terms) + 1)

    a_tokens = [tok for t in terms for tok in _term_occurrences(t, tf_a[t], draw)]
    b_tokens = [tok for t in terms for tok in _term_occurrences(t, tf_b[t], draw)]
    doc_a = _assemble(a_tokens + [filler] * (n - len(a_tokens)), draw)
    doc_b = _assemble(b_tokens + [filler] * (n - len(b_tokens)), draw)
    return terms, tf_a, tf_b, n, doc_a, doc_b


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 15: BM25 ranking sanity
# Validates: Requirements 7.5
@settings(max_examples=200, deadline=None)
@given(case=_equal_length_single_term())
def test_property15_single_term_tf_monotonicity(
    case: tuple[str, int, int, int, str, str],
) -> None:
    q, tf_a, tf_b, n, doc_a, doc_b = case

    # The query term survives sanitization unchanged, so term_frequency counts
    # what the FTS layer indexes.
    assert build_tsquery_terms(q) == [q]

    # The real helper recovers the controlled occurrence counts (case-insensitive).
    counted_a = term_frequency(q, doc_a)
    counted_b = term_frequency(q, doc_b)
    assert counted_a == tf_a
    assert counted_b == tf_b

    # All-else-equal: both docs have the same token length n.
    score_a = _bm25_score({q: counted_a}, doc_len=n, avg_len=n)
    score_b = _bm25_score({q: counted_b}, doc_len=n, avg_len=n)

    # Higher (or equal) term frequency must rank at least as high.
    if counted_a >= counted_b:
        assert score_a >= score_b
        assert bm25_sanity_holds(score_a, score_b)
    if counted_b >= counted_a:
        assert score_b >= score_a
        assert bm25_sanity_holds(score_b, score_a)


# Feature: rag-knowledge-pipeline, Property 15: BM25 ranking sanity
# Validates: Requirements 7.5
@settings(max_examples=200, deadline=None)
@given(case=_zero_term_vs_present())
def test_property15_absent_term_never_outranks(
    case: tuple[str, int, int, str, str],
) -> None:
    q, tf_a, n, doc_with, doc_without = case

    assert build_tsquery_terms(q) == [q]
    assert term_frequency(q, doc_with) == tf_a
    # The doc lacking the term has zero occurrences of it.
    assert term_frequency(q, doc_without) == 0

    score_with = _bm25_score({q: term_frequency(q, doc_with)}, doc_len=n, avg_len=n)
    score_without = _bm25_score({q: term_frequency(q, doc_without)}, doc_len=n, avg_len=n)

    # A doc containing the favorable-IDF term strictly out-scores one that does
    # not (tf>=1 vs tf==0), so the term-bearing doc ranks at least as high...
    assert bm25_sanity_holds(score_with, score_without)
    assert score_with > score_without
    # ...and the term-less doc does NOT outrank the term-bearing one.
    assert not bm25_sanity_holds(score_without, score_with)


# Feature: rag-knowledge-pipeline, Property 15: BM25 ranking sanity
# Validates: Requirements 7.5
@settings(max_examples=200, deadline=None)
@given(case=_coverage_multi_term())
def test_property15_multi_term_coverage_monotonicity(
    case: tuple[list[str], dict[str, int], dict[str, int], int, str, str],
) -> None:
    terms, tf_a, tf_b, n, doc_a, doc_b = case

    # term_frequency recovers each per-term controlled count in both docs.
    counted_a = {t: term_frequency(t, doc_a) for t in terms}
    counted_b = {t: term_frequency(t, doc_b) for t in terms}
    assert counted_a == tf_a
    assert counted_b == tf_b

    # Doc A covers a superset (>= occurrences of every query term).
    assert all(counted_a[t] >= counted_b[t] for t in terms)

    # Equal-length docs -> better coverage ranks at least as high.
    score_a = _bm25_score(counted_a, doc_len=n, avg_len=n)
    score_b = _bm25_score(counted_b, doc_len=n, avg_len=n)
    assert score_a >= score_b
    assert bm25_sanity_holds(score_a, score_b)


# ---------------------------------------------------------------------------
# Focused example-based unit tests for the pure helpers (complement the PBT)
# ---------------------------------------------------------------------------


def test_term_frequency_counts_whole_tokens_case_insensitively() -> None:
    text = "Aspirin aspirin ASPIRIN buffered-aspirin tablet"
    # 3 standalone whole-token occurrences; "buffered-aspirin" splits into two
    # tokens "buffered" and "aspirin", so it contributes one more.
    assert term_frequency("aspirin", text) == 4
    assert term_frequency("ASPIRIN", text) == 4
    assert term_frequency("tablet", text) == 1
    assert term_frequency("ibuprofen", text) == 0


def test_term_frequency_empty_inputs() -> None:
    assert term_frequency("", "anything here") == 0
    assert term_frequency("aspirin", "") == 0


def test_bm25_sanity_holds_ordering() -> None:
    # >= relationship is exactly the Property 15 ordering invariant.
    assert bm25_sanity_holds(2.0, 1.0) is True
    assert bm25_sanity_holds(1.0, 1.0) is True
    assert bm25_sanity_holds(0.0, 1.0) is False
