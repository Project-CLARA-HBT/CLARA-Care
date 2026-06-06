"""Retrieval and answer-quality metrics for the RAG eval harness (Epic P5).

This module is the pure, stdlib-only scoring core of the evaluation harness. It
contains four deterministic functions, each returning a value in the closed
interval ``[0, 1]``:

- :func:`recall_at_k` — retrieval coverage of gold-relevant ids in the top ``k``.
- :func:`ndcg_at_k` — rank-sensitive retrieval quality (binary-gain nDCG).
- :func:`faithfulness` — fraction of answer sentences supported by retrieved text.
- :func:`citation_accuracy` — fraction of required citations actually produced.

Design constraints (task 9.2 / Requirements 11.2):

- **Pure & deterministic.** No I/O, no globals, no randomness, no clocks. The
  same inputs always yield the same output, so results are reproducible in CI.
- **Import-safe.** Importing this module has no side effects and pulls in only
  the Python standard library (``math``, ``re``).
- **Bounded.** Every function is mathematically constrained to ``[0, 1]`` and
  additionally clamps its result as a defensive backstop.
- **Documented edge cases.** Empty / degenerate inputs resolve to ``0.0`` or
  ``1.0`` per the rules documented on each function (see the per-function
  "Edge cases" sections below).

Ranked-list inputs are de-duplicated preserving first-seen order before scoring.
A retrieval system returning the same id twice should not be able to inflate
``recall@k`` / ``nDCG@k`` past the bound, so each unique id is counted once at
its earliest rank.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence

__all__ = [
    "recall_at_k",
    "ndcg_at_k",
    "faithfulness",
    "citation_accuracy",
]

# Token surface shared with the reranker's lexical heuristic: alphanumeric runs
# of length >= 2 including Vietnamese accented letters (range À-ỹ). Lowercased
# at call sites for case-insensitive comparison.
_TOKEN_RE = re.compile(r"[0-9a-zA-ZÀ-ỹ]{2,}")

# Sentence boundaries: terminal punctuation (Latin + Vietnamese share these) and
# newlines. Used only by :func:`faithfulness`.
_SENTENCE_SPLIT_RE = re.compile(r"[.!?;\n\r]+")

# Default fraction of a sentence's key terms that must appear in the retrieved
# context for that sentence to count as "supported" in :func:`faithfulness`.
_DEFAULT_FAITHFULNESS_MIN_COVERAGE = 0.6


def _clamp_unit(value: float) -> float:
    """Clamp ``value`` into the closed interval ``[0, 1]`` (defensive backstop)."""

    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return float(value)


def _dedupe_preserving_order(ids: Iterable[object]) -> list[str]:
    """Return ids as strings, de-duplicated, preserving first-seen order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for raw in ids:
        key = str(raw)
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _tokens(text: str) -> set[str]:
    """Lowercase key-term token set extracted from ``text`` (empty for blanks)."""

    return {match.lower() for match in _TOKEN_RE.findall(str(text or ""))}


def recall_at_k(
    ranked_ids: Sequence[object],
    relevant_ids: Iterable[object],
    k: int,
) -> float:
    """Recall@k: fraction of gold-relevant ids retrieved within the top ``k``.

    Formula::

        recall@k = |relevant ∩ top_k(ranked_ids)| / |relevant|

    where ``top_k`` is the first ``k`` *unique* ids of ``ranked_ids`` (duplicates
    are collapsed to their earliest rank) and ``relevant`` is the set of gold ids.
    Ids are compared as strings.

    Edge cases (documented):
    - No relevant ids (``relevant`` empty) -> ``0.0``. The ratio is otherwise
      undefined (``0/0``); the spec fixes it to ``0.0``.
    - ``k <= 0`` -> empty top-k -> ``0.0``.
    - ``ranked_ids`` empty -> ``0.0`` (unless there are also no relevant ids,
      which already returns ``0.0``).

    The result is always in ``[0, 1]`` because the numerator (a set intersection)
    can never exceed the denominator (the relevant set size).
    """

    relevant = {str(rid) for rid in relevant_ids}
    if not relevant:
        return 0.0
    if k <= 0:
        return 0.0

    top_k = _dedupe_preserving_order(ranked_ids)[:k]
    hit = sum(1 for cid in top_k if cid in relevant)
    return _clamp_unit(hit / len(relevant))


def ndcg_at_k(
    ranked_ids: Sequence[object],
    relevant_ids: Iterable[object],
    k: int,
) -> float:
    """nDCG@k with binary gains, normalized by the ideal DCG.

    Gains are binary: an id contributes gain ``1`` if it is in ``relevant_ids``,
    else ``0``. With the standard log2 discount and 0-based rank ``i``::

        DCG@k  = Σ_{i<k}  rel(top_k[i]) / log2(i + 2)
        IDCG@k = Σ_{i<m}  1 / log2(i + 2),  m = min(k, |relevant|)
        nDCG@k = DCG@k / IDCG@k

    ``ranked_ids`` is de-duplicated preserving first-seen order before scoring, so
    each unique relevant id contributes at most once and ``DCG@k <= IDCG@k`` always
    holds — the result stays in ``[0, 1]``.

    Edge cases (documented):
    - No relevant ids -> ``0.0`` (``IDCG`` is ``0``; ratio defined as ``0.0``).
    - ``k <= 0`` -> ``0.0`` (empty window, ``IDCG`` is ``0``).
    - No relevant id appears in the top-k window -> ``DCG`` is ``0`` -> ``0.0``.
    """

    relevant = {str(rid) for rid in relevant_ids}
    if not relevant or k <= 0:
        return 0.0

    top_k = _dedupe_preserving_order(ranked_ids)[:k]
    dcg = 0.0
    for index, cid in enumerate(top_k):
        if cid in relevant:
            dcg += 1.0 / math.log2(index + 2)

    ideal_hits = min(k, len(relevant))
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    if idcg <= 0.0:
        return 0.0
    return _clamp_unit(dcg / idcg)


def faithfulness(
    answer: str,
    retrieved_texts: Sequence[str],
    *,
    min_coverage: float = _DEFAULT_FAITHFULNESS_MIN_COVERAGE,
) -> float:
    """Faithfulness: fraction of answer sentences supported by retrieved context.

    Operationalization (deterministic, sentence-level term coverage):

    1. Split ``answer`` into sentences on terminal punctuation (``. ! ? ;``) and
       newlines.
    2. For each sentence, extract its key-term set (lowercased alphanumeric runs
       of length >= 2, Vietnamese accents included). Sentences with no key terms
       carry no claim and are ignored.
    3. Build the context term set from the union of all ``retrieved_texts``.
    4. A sentence is **supported** when the fraction of its key terms present in
       the context is ``>= min_coverage``.
    5. Return ``supported_sentences / claim_bearing_sentences``.

    This is a recall-of-claim-terms proxy for "are the answer's claims grounded
    in what was retrieved"; it is intentionally lexical (no model call) so it is
    pure and reproducible in CI.

    Edge cases (documented):
    - ``answer`` has no claim-bearing sentences (empty / punctuation-only) ->
      ``1.0`` (vacuously faithful: there is nothing unsupported to penalize).
    - ``answer`` has claims but ``retrieved_texts`` is empty / blank -> ``0.0``
      (no context can support any claim).
    - ``min_coverage`` is clamped into ``[0, 1]`` before use.

    The result is always in ``[0, 1]`` (a ratio of a subset count to a total).
    """

    coverage_threshold = _clamp_unit(min_coverage)

    sentences = _SENTENCE_SPLIT_RE.split(str(answer or ""))
    claim_term_sets = [terms for terms in (_tokens(sentence) for sentence in sentences) if terms]
    if not claim_term_sets:
        # No claims at all -> nothing can be unsupported.
        return 1.0

    context_terms: set[str] = set()
    for text in retrieved_texts:
        context_terms |= _tokens(text)
    if not context_terms:
        return 0.0

    supported = 0
    for terms in claim_term_sets:
        covered = sum(1 for term in terms if term in context_terms)
        if (covered / len(terms)) >= coverage_threshold:
            supported += 1

    return _clamp_unit(supported / len(claim_term_sets))


def citation_accuracy(
    cited_ids: Iterable[object],
    must_cite_ids: Iterable[object],
) -> float:
    """Citation accuracy: fraction of required citations actually produced.

    Formula (recall of the required-citation set)::

        citation_accuracy = |cited ∩ must_cite| / |must_cite|

    Ids are compared as strings; ``cited_ids`` is treated as a set so repeating a
    citation neither helps nor hurts. Extra (non-required) citations are ignored
    — this measures coverage of the gold ``must_cite`` targets, not precision.

    Edge cases (documented):
    - ``must_cite`` empty -> ``1.0`` (no required citations; all zero of them are
      trivially satisfied).
    - ``cited`` empty while ``must_cite`` is non-empty -> ``0.0``.

    The result is always in ``[0, 1]`` because the numerator (a set intersection)
    can never exceed the denominator (the required-citation set size).
    """

    must_cite = {str(mid) for mid in must_cite_ids}
    if not must_cite:
        return 1.0

    cited = {str(cid) for cid in cited_ids}
    satisfied = len(cited & must_cite)
    return _clamp_unit(satisfied / len(must_cite))
