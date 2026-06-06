"""Unit tests for the RAG eval metric bounds and known values (task 9.3).

Targets the pure scoring functions in ``clara_ml.rag.eval.metrics``:

* :func:`recall_at_k`
* :func:`ndcg_at_k`
* :func:`faithfulness`
* :func:`citation_accuracy`

The design (Requirement 11.2) requires each metric to be bounded in the closed
interval ``[0, 1]``. These parametrized unit tests check three things:

1. **Known small examples** produce the expected values.
2. **All outputs** stay within ``[0, 1]`` across a spread of inputs.
3. **Documented edge cases** resolve as specified (empty relevant -> 0.0;
   empty must_cite -> 1.0; ``k <= 0`` -> 0.0; empty answer -> faithfulness 1.0
   vacuously).
"""

from __future__ import annotations

import pytest

from clara_ml.rag.eval.metrics import (
    citation_accuracy,
    faithfulness,
    ndcg_at_k,
    recall_at_k,
)

# A small absolute tolerance for floating-point ratio comparisons.
_TOL = 1e-9


def _in_unit_interval(value: float) -> bool:
    """True iff ``value`` lies in the closed interval ``[0, 1]``."""

    return 0.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# recall_at_k — known values
# ---------------------------------------------------------------------------


def test_recall_at_k_known_example_half() -> None:
    # recall@2 of [a, b, c] vs relevant {b, d}: only b is in top-2 of two gold
    # ids -> 1/2 == 0.5.
    assert recall_at_k(["a", "b", "c"], {"b", "d"}, 2) == pytest.approx(0.5, abs=_TOL)


def test_recall_at_k_all_relevant_retrieved() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, 3) == pytest.approx(1.0, abs=_TOL)


def test_recall_at_k_none_retrieved_in_window() -> None:
    # Relevant id "c" is outside the top-2 window.
    assert recall_at_k(["a", "b", "c"], {"c"}, 2) == pytest.approx(0.0, abs=_TOL)


def test_recall_at_k_dedupes_ranked_ids() -> None:
    # Duplicate "a" collapses to its earliest rank; the top-2 unique window is
    # [a, b], so both gold ids are found -> 1.0 (a duplicate cannot inflate or
    # crowd out coverage).
    assert recall_at_k(["a", "a", "b"], {"a", "b"}, 2) == pytest.approx(1.0, abs=_TOL)


@pytest.mark.parametrize(
    ("ranked", "relevant", "k", "expected"),
    [
        (["a", "b", "c"], {"b", "d"}, 2, 0.5),
        (["a", "b", "c", "d"], {"a", "b", "c", "d"}, 4, 1.0),
        (["x", "y"], {"a", "b"}, 5, 0.0),
        ([1, 2, 3], {2, 3}, 3, 1.0),  # non-string ids compared as strings
    ],
)
def test_recall_at_k_parametrized_values(
    ranked: list[object],
    relevant: set[object],
    k: int,
    expected: float,
) -> None:
    assert recall_at_k(ranked, relevant, k) == pytest.approx(expected, abs=_TOL)


# recall_at_k — documented edge cases


@pytest.mark.parametrize("k", [0, -1, -10])
def test_recall_at_k_non_positive_k_is_zero(k: int) -> None:
    assert recall_at_k(["a", "b"], {"a"}, k) == 0.0


def test_recall_at_k_empty_relevant_is_zero() -> None:
    assert recall_at_k(["a", "b"], set(), 2) == 0.0


def test_recall_at_k_empty_ranked_is_zero() -> None:
    assert recall_at_k([], {"a"}, 2) == 0.0


# ---------------------------------------------------------------------------
# ndcg_at_k — known values
# ---------------------------------------------------------------------------


def test_ndcg_at_k_ideal_ordering_is_one() -> None:
    # All relevant ids ranked first in the ideal order -> nDCG == 1.0.
    assert ndcg_at_k(["a", "b", "c"], {"a", "b"}, 3) == pytest.approx(1.0, abs=_TOL)


def test_ndcg_at_k_worse_ordering_is_strictly_less_than_one() -> None:
    ideal = ndcg_at_k(["a", "b", "c"], {"a", "b"}, 3)
    worse = ndcg_at_k(["c", "a", "b"], {"a", "b"}, 3)
    assert ideal == pytest.approx(1.0, abs=_TOL)
    assert worse < 1.0
    assert _in_unit_interval(worse)


def test_ndcg_at_k_single_relevant_at_top_is_one() -> None:
    assert ndcg_at_k(["a", "b", "c"], {"a"}, 3) == pytest.approx(1.0, abs=_TOL)


def test_ndcg_at_k_dedupes_ranked_ids() -> None:
    # Duplicate relevant id cannot push DCG above the ideal -> stays 1.0.
    assert ndcg_at_k(["a", "a", "b"], {"a", "b"}, 3) == pytest.approx(1.0, abs=_TOL)


@pytest.mark.parametrize(
    ("ranked", "relevant", "k"),
    [
        (["a", "b", "c"], {"a", "b"}, 3),
        (["c", "a", "b"], {"a", "b"}, 3),
        (["a", "b", "c", "d"], {"b", "d"}, 4),
        (["d", "c", "b", "a"], {"a"}, 4),
    ],
)
def test_ndcg_at_k_bounded(ranked: list[object], relevant: set[object], k: int) -> None:
    assert _in_unit_interval(ndcg_at_k(ranked, relevant, k))


# ndcg_at_k — documented edge cases


@pytest.mark.parametrize("k", [0, -1, -5])
def test_ndcg_at_k_non_positive_k_is_zero(k: int) -> None:
    assert ndcg_at_k(["a", "b"], {"a"}, k) == 0.0


def test_ndcg_at_k_empty_relevant_is_zero() -> None:
    assert ndcg_at_k(["a", "b"], set(), 2) == 0.0


def test_ndcg_at_k_no_relevant_in_window_is_zero() -> None:
    assert ndcg_at_k(["x", "y"], {"a", "b"}, 2) == 0.0


# ---------------------------------------------------------------------------
# faithfulness — known values
# ---------------------------------------------------------------------------


def test_faithfulness_fully_supported_is_one() -> None:
    answer = "Paracetamol relieves pain. Paracetamol reduces fever."
    context = ["Paracetamol relieves pain and reduces fever in adults."]
    assert faithfulness(answer, context) == pytest.approx(1.0, abs=_TOL)


def test_faithfulness_fully_unsupported_is_zero() -> None:
    answer = "Ibuprofen causes drowsiness and blurred vision."
    context = ["Completely unrelated text about gardening and weather."]
    assert faithfulness(answer, context) == pytest.approx(0.0, abs=_TOL)


def test_faithfulness_partial_support_is_between() -> None:
    answer = "Paracetamol relieves pain. Ibuprofen cures cancer overnight."
    context = ["Paracetamol relieves pain in adults."]
    score = faithfulness(answer, context)
    assert score == pytest.approx(0.5, abs=_TOL)
    assert _in_unit_interval(score)


@pytest.mark.parametrize(
    ("answer", "context"),
    [
        ("Paracetamol relieves pain.", ["Paracetamol relieves pain."]),
        ("Random claim here.", ["Totally different content."]),
        ("Mixed claim one. Mixed claim two.", ["Mixed claim one only."]),
        ("Thuốc giảm đau hiệu quả.", ["Thuốc giảm đau hiệu quả cho người lớn."]),
    ],
)
def test_faithfulness_bounded(answer: str, context: list[str]) -> None:
    assert _in_unit_interval(faithfulness(answer, context))


# faithfulness — documented edge cases


@pytest.mark.parametrize("answer", ["", "   ", "...", "!?;\n", "\n\r"])
def test_faithfulness_no_claims_is_vacuously_one(answer: str) -> None:
    # No claim-bearing sentences -> nothing unsupported -> 1.0 (vacuous).
    assert faithfulness(answer, ["some context"]) == 1.0


def test_faithfulness_empty_context_with_claims_is_zero() -> None:
    assert faithfulness("Some real claim here.", []) == 0.0


def test_faithfulness_blank_context_with_claims_is_zero() -> None:
    assert faithfulness("Some real claim here.", ["", "   "]) == 0.0


def test_faithfulness_empty_answer_and_empty_context_is_one() -> None:
    # No claims dominates: vacuously faithful even with no context.
    assert faithfulness("", []) == 1.0


# ---------------------------------------------------------------------------
# citation_accuracy — known values
# ---------------------------------------------------------------------------


def test_citation_accuracy_full_is_one() -> None:
    assert citation_accuracy(["a", "b", "c"], ["a", "b"]) == pytest.approx(1.0, abs=_TOL)


def test_citation_accuracy_partial_is_half() -> None:
    assert citation_accuracy(["a", "z"], ["a", "b"]) == pytest.approx(0.5, abs=_TOL)


def test_citation_accuracy_empty_cited_with_requirements_is_zero() -> None:
    assert citation_accuracy([], ["a", "b"]) == pytest.approx(0.0, abs=_TOL)


def test_citation_accuracy_ignores_extra_and_duplicate_citations() -> None:
    # Extra ("x") and duplicate ("a") citations neither help nor hurt.
    assert citation_accuracy(["a", "a", "x"], ["a"]) == pytest.approx(1.0, abs=_TOL)


@pytest.mark.parametrize(
    ("cited", "must_cite", "expected"),
    [
        (["a", "b"], ["a", "b"], 1.0),
        (["a"], ["a", "b"], 0.5),
        ([], ["a", "b"], 0.0),
        ([1, 2], [2, 3], 0.5),  # non-string ids compared as strings
    ],
)
def test_citation_accuracy_parametrized_values(
    cited: list[object],
    must_cite: list[object],
    expected: float,
) -> None:
    assert citation_accuracy(cited, must_cite) == pytest.approx(expected, abs=_TOL)


# citation_accuracy — documented edge cases


def test_citation_accuracy_empty_must_cite_is_one() -> None:
    # No required citations -> trivially satisfied -> 1.0.
    assert citation_accuracy(["a", "b"], []) == 1.0


def test_citation_accuracy_empty_must_cite_and_empty_cited_is_one() -> None:
    assert citation_accuracy([], []) == 1.0


# ---------------------------------------------------------------------------
# Cross-metric bounds sweep — every output stays within [0, 1]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("k", [0, 1, 2, 3, 5, 10])
@pytest.mark.parametrize(
    ("ranked", "relevant"),
    [
        ([], set()),
        ([], {"a"}),
        (["a"], set()),
        (["a", "b", "c"], {"a"}),
        (["a", "b", "c"], {"a", "b", "c"}),
        (["a", "a", "b"], {"a", "b"}),
        (["x", "y", "z"], {"a", "b"}),
    ],
)
def test_recall_and_ndcg_always_bounded(
    ranked: list[object],
    relevant: set[object],
    k: int,
) -> None:
    assert _in_unit_interval(recall_at_k(ranked, relevant, k))
    assert _in_unit_interval(ndcg_at_k(ranked, relevant, k))


@pytest.mark.parametrize(
    ("cited", "must_cite"),
    [
        ([], []),
        ([], ["a"]),
        (["a"], []),
        (["a", "b"], ["a", "b", "c"]),
        (["a", "a"], ["a"]),
        (["x"], ["a", "b"]),
    ],
)
def test_citation_accuracy_always_bounded(
    cited: list[object],
    must_cite: list[object],
) -> None:
    assert _in_unit_interval(citation_accuracy(cited, must_cite))
