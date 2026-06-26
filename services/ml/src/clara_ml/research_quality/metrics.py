"""Research-quality metrics for the CLARA Research golden-set harness (Epic 15, R17).

This module is the pure, stdlib-only scoring core of the *research* quality
harness. It mirrors the design conventions of :mod:`clara_ml.rag.eval.metrics`
(import-safe, deterministic, ``[0, 1]``-bounded, documented edge cases) but adds
the two research-specific metrics that the rag eval harness does not carry:
``unsupported_claim_rate`` and ``refusal_compliance``.

The five functions implement Requirement 17.2 ("compute recall@k, faithfulness,
citation_accuracy, unsupported-claim rate, and refusal compliance"):

- :func:`recall_at_k` — retrieval coverage of gold-relevant ids in the top ``k``.
- :func:`faithfulness` — fraction of answer sentences supported by retrieved text.
- :func:`citation_accuracy` — fraction of required citations actually produced.
- :func:`unsupported_claim_rate` — fraction of answer claims NOT grounded in the
  retrieved evidence (the faithfulness complement, reported as a *rate*).
- :func:`refusal_compliance` — whether the system's refusal decision matched the
  golden item's expected refusal decision.

Design constraints (Requirement 17.2):

- **Pure & deterministic.** No I/O, no globals, no randomness, no clocks; same
  inputs always yield the same output, so results are reproducible in CI.
- **Import-safe.** Importing this module has no side effects and pulls in only
  the Python standard library (``re``).
- **Bounded.** Every function is mathematically constrained to ``[0, 1]`` and
  additionally clamps its result as a defensive backstop.
- **Documented edge cases.** Empty / degenerate inputs resolve to ``0.0`` or
  ``1.0`` per the rules documented on each function.

Ranked-list inputs are de-duplicated preserving first-seen order before scoring,
so a retrieval system returning the same id twice cannot inflate ``recall@k``.

Validates: Requirements 17.1, 17.2.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

__all__ = [
    "recall_at_k",
    "faithfulness",
    "citation_accuracy",
    "unsupported_claim_rate",
    "refusal_compliance",
]

# Token surface shared with the rag eval metrics: alphanumeric runs of length
# >= 2 including Vietnamese accented letters (range À-ỹ). Lowercased at call
# sites for case-insensitive comparison.
_TOKEN_RE = re.compile(r"[0-9a-zA-ZÀ-ỹ]{2,}")

# Sentence boundaries: terminal punctuation (Latin + Vietnamese share these) and
# newlines. Used by :func:`faithfulness` and :func:`unsupported_claim_rate`.
_SENTENCE_SPLIT_RE = re.compile(r"[.!?;\n\r]+")

# Default fraction of a sentence's key terms that must appear in the retrieved
# context for that sentence to count as "supported".
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


def _claim_term_sets(answer: str) -> list[set[str]]:
    """Key-term sets for each claim-bearing sentence in ``answer``.

    A sentence carries a claim when it has at least one key term; punctuation-
    only or empty sentences are dropped.
    """

    sentences = _SENTENCE_SPLIT_RE.split(str(answer or ""))
    return [terms for terms in (_tokens(sentence) for sentence in sentences) if terms]


def _context_terms(retrieved_texts: Sequence[str]) -> set[str]:
    """Union of key terms across all retrieved context texts."""

    context: set[str] = set()
    for text in retrieved_texts:
        context |= _tokens(text)
    return context


def recall_at_k(
    ranked_ids: Sequence[object],
    relevant_ids: Iterable[object],
    k: int,
) -> float:
    """Recall@k: fraction of gold-relevant ids retrieved within the top ``k``.

    Formula::

        recall@k = |relevant ∩ top_k(ranked_ids)| / |relevant|

    where ``top_k`` is the first ``k`` *unique* ids of ``ranked_ids`` (duplicates
    collapsed to their earliest rank) and ``relevant`` is the gold id set. Ids
    are compared as strings.

    Edge cases (documented):
    - No relevant ids -> ``0.0`` (the ratio ``0/0`` is fixed to ``0.0``).
    - ``k <= 0`` -> empty top-k -> ``0.0``.
    - ``ranked_ids`` empty -> ``0.0``.

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


def faithfulness(
    answer: str,
    retrieved_texts: Sequence[str],
    *,
    min_coverage: float = _DEFAULT_FAITHFULNESS_MIN_COVERAGE,
) -> float:
    """Faithfulness: fraction of answer sentences supported by retrieved context.

    Operationalization (deterministic, sentence-level term coverage):

    1. Split ``answer`` into sentences on terminal punctuation and newlines.
    2. For each sentence, extract its key-term set (lowercased alphanumeric runs
       of length >= 2, Vietnamese accents included). Sentences with no key terms
       carry no claim and are ignored.
    3. Build the context term set from the union of all ``retrieved_texts``.
    4. A sentence is **supported** when the fraction of its key terms present in
       the context is ``>= min_coverage``.
    5. Return ``supported_sentences / claim_bearing_sentences``.

    Edge cases (documented):
    - ``answer`` has no claim-bearing sentences -> ``1.0`` (vacuously faithful).
    - ``answer`` has claims but ``retrieved_texts`` is empty / blank -> ``0.0``.
    - ``min_coverage`` is clamped into ``[0, 1]`` before use.

    The result is always in ``[0, 1]``.
    """

    coverage_threshold = _clamp_unit(min_coverage)

    claim_term_sets = _claim_term_sets(answer)
    if not claim_term_sets:
        return 1.0

    context_terms = _context_terms(retrieved_texts)
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
    citation neither helps nor hurts. Extra citations are ignored — this measures
    coverage of the gold ``must_cite`` targets, not precision.

    Edge cases (documented):
    - ``must_cite`` empty -> ``1.0`` (no required citations to satisfy).
    - ``cited`` empty while ``must_cite`` is non-empty -> ``0.0``.

    The result is always in ``[0, 1]``.
    """

    must_cite = {str(mid) for mid in must_cite_ids}
    if not must_cite:
        return 1.0

    cited = {str(cid) for cid in cited_ids}
    satisfied = len(cited & must_cite)
    return _clamp_unit(satisfied / len(must_cite))


def unsupported_claim_rate(
    answer: str,
    retrieved_texts: Sequence[str],
    *,
    min_coverage: float = _DEFAULT_FAITHFULNESS_MIN_COVERAGE,
) -> float:
    """Unsupported-claim rate: fraction of answer claims NOT grounded in evidence.

    This is the faithfulness complement, reported as a *rate* (lower is better).
    Using the same sentence-level term-coverage operationalization as
    :func:`faithfulness`, a claim-bearing sentence is **unsupported** when the
    fraction of its key terms present in the retrieved context is
    ``< min_coverage``. The metric returns::

        unsupported_claim_rate = unsupported_claims / claim_bearing_claims

    Edge cases (documented):
    - ``answer`` has no claim-bearing sentences -> ``0.0`` (no claim can be
      unsupported; nothing to penalize).
    - ``answer`` has claims but ``retrieved_texts`` is empty / blank -> ``1.0``
      (no context can support any claim, so every claim is unsupported).
    - ``min_coverage`` is clamped into ``[0, 1]`` before use.

    The result is always in ``[0, 1]`` and equals ``1 - faithfulness`` on every
    answer that carries at least one claim.
    """

    coverage_threshold = _clamp_unit(min_coverage)

    claim_term_sets = _claim_term_sets(answer)
    if not claim_term_sets:
        return 0.0

    context_terms = _context_terms(retrieved_texts)
    if not context_terms:
        return 1.0

    unsupported = 0
    for terms in claim_term_sets:
        covered = sum(1 for term in terms if term in context_terms)
        if (covered / len(terms)) < coverage_threshold:
            unsupported += 1

    return _clamp_unit(unsupported / len(claim_term_sets))


def refusal_compliance(did_refuse: bool, should_refuse: bool) -> float:
    """Refusal compliance: did the refusal decision match the expected decision?

    The golden set marks each item with whether the system *should* refuse it
    (e.g. an out-of-scope query — Requirement 10.5). Compliance is a per-item
    correctness indicator:

    - ``1.0`` when the observed refusal decision equals the expected decision
      (a correct refusal of an out-of-scope query, or a correct non-refusal of
      an in-scope query); and
    - ``0.0`` otherwise (a missed refusal or an over-refusal).

    Coercing both arguments to ``bool`` keeps the comparison total. Aggregating
    this metric (mean across the golden set) yields the overall refusal-
    compliance score the gate consumes.

    The result is always in ``{0.0, 1.0}`` ⊂ ``[0, 1]``.
    """

    return 1.0 if bool(did_refuse) == bool(should_refuse) else 0.0
