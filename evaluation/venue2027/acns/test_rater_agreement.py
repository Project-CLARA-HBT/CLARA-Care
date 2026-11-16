"""Tests for ACNS-X06_adjudication inter-rater agreement module.

Verifies:
- Positive controls:
  - Perfect agreement produces Krippendorff alpha == 1.0 and Cohen kappa == 1.0
  - Complete pairs match known Cohen kappa formula across textbook and manual benchmarks
  - Bootstrap CI bounds are valid and deterministic by seed
  - measure() contract compatibility
  - JSON serializability
- Adversarial controls:
  - Empty ratings matrices refused fail-closed with stable reason code
  - Insufficient raters (<2) and unpairable matrices refused fail-closed
  - All-disagreement matrices handled correctly (alpha <= 0.0, no NaN or unhandled error)
  - Missing labels (None, empty string, float('nan')) handled gracefully without NaN crash
"""

from __future__ import annotations

import json
import math

import pytest

from evaluation.venue2027.acns.rater_agreement import (
    Agreement,
    AgreementResult,
    RaterAgreementError,
    compute_agreement,
    measure,
)

# ==============================================================================
# Positive Controls
# ==============================================================================


def test_perfect_agreement_two_raters() -> None:
    """Perfect agreement across two raters yields alpha=1.0, kappa=1.0, CI=[1, 1]."""
    matrix = [
        ["VALID", "VALID"],
        ["OVERREAD", "OVERREAD"],
        ["UNDERREAD", "UNDERREAD"],
        ["INDETERMINATE", "INDETERMINATE"],
    ] * 5
    res = compute_agreement(matrix, num_bootstraps=200, seed=2027)

    assert isinstance(res, AgreementResult)
    assert res.krippendorff_alpha == pytest.approx(1.0)
    assert res.cohen_kappa == pytest.approx(1.0)
    assert res.ci_lower == pytest.approx(1.0)
    assert res.ci_upper == pytest.approx(1.0)
    assert res.reason_code == "OK"
    assert res.num_units == 20
    assert res.num_raters == 2


def test_perfect_agreement_multiple_raters() -> None:
    """Perfect agreement across 4 raters yields alpha=1.0 and cohen_kappa=None."""
    matrix = [
        ["A", "A", "A", "A"],
        ["B", "B", "B", "B"],
        ["C", "C", "C", "C"],
    ] * 6
    res = compute_agreement(matrix, num_bootstraps=200, seed=2027)

    assert res.krippendorff_alpha == pytest.approx(1.0)
    assert res.cohen_kappa is None  # Cohen's kappa is strictly for 2 raters
    assert res.ci_lower == pytest.approx(1.0)
    assert res.ci_upper == pytest.approx(1.0)
    assert res.num_raters == 4


def test_perfect_agreement_single_category() -> None:
    """Consensus where all ratings are the identical category yields alpha=1.0 and kappa=1.0."""
    matrix = [["VALID", "VALID"]] * 15
    res = compute_agreement(matrix, num_bootstraps=100, seed=2027)

    assert res.krippendorff_alpha == pytest.approx(1.0)
    assert res.cohen_kappa == pytest.approx(1.0)
    assert res.ci_lower == pytest.approx(1.0)
    assert res.ci_upper == pytest.approx(1.0)


def test_complete_pairs_match_known_cohen_kappa() -> None:
    """Complete pairs match known analytical Cohen kappa formula values."""
    # Benchmark 1: 10 units
    # Rater A: 6 ones, 4 zeros (p=0.6)
    # Rater B: 6 ones, 4 zeros (p=0.6)
    # Agreements: 8 out of 10 (Po = 0.8)
    # Pe = 0.6*0.6 + 0.4*0.4 = 0.52
    # Kappa = (0.8 - 0.52) / (1.0 - 0.52) = 0.28 / 0.48 = 7 / 12 ≈ 0.5833333333
    matrix_1 = [
        [1, 1],
        [1, 1],
        [1, 1],
        [1, 1],
        [1, 0],
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 1],
        [1, 1],
    ]
    res_1 = compute_agreement(matrix_1, num_bootstraps=50, seed=2027)
    assert res_1.cohen_kappa == pytest.approx(7.0 / 12.0)

    # Benchmark 2: 30 units with 4 cells:
    # 10 (A, A), 5 (A, B), 3 (B, A), 12 (B, B)
    # Po = 22 / 30 = 11 / 15
    # Rater 1: 15 A, 15 B -> P1 = 0.5, 0.5
    # Rater 2: 13 A, 17 B -> P2 = 13/30, 17/30
    # Pe = 0.5*(13/30) + 0.5*(17/30) = 0.5
    # Kappa = (11/15 - 0.5) / (1.0 - 0.5) = (7/30) / (1/2) = 7/15 ≈ 0.4666666667
    matrix_2 = [["A", "A"]] * 10 + [["A", "B"]] * 5 + [["B", "A"]] * 3 + [["B", "B"]] * 12
    res_2 = compute_agreement(matrix_2, num_bootstraps=50, seed=2027)
    assert res_2.cohen_kappa == pytest.approx(7.0 / 15.0)


def test_bootstrap_ci_bounds_correct_and_deterministic() -> None:
    """Bootstrap CI bounds enclose point estimate and are deterministic with seed."""
    matrix = (
        [["VALID", "VALID"]] * 14
        + [["VALID", "OVERREAD"]] * 3
        + [["OVERREAD", "OVERREAD"]] * 8
        + [["UNDERREAD", "UNDERREAD"]] * 5
    )
    res_a = compute_agreement(matrix, num_bootstraps=500, seed=2027)
    res_b = compute_agreement(matrix, num_bootstraps=500, seed=2027)

    # Determinism
    assert res_a.krippendorff_alpha == res_b.krippendorff_alpha
    assert res_a.ci_lower == res_b.ci_lower
    assert res_a.ci_upper == res_b.ci_upper

    # Validity of interval
    assert res_a.ci_lower <= res_a.krippendorff_alpha <= res_a.ci_upper
    assert res_a.ci_lower < res_a.ci_upper

    # Different seed yields slightly different but valid interval
    res_diff_seed = compute_agreement(matrix, num_bootstraps=500, seed=42)
    assert res_diff_seed.ci_lower <= res_diff_seed.krippendorff_alpha <= res_diff_seed.ci_upper


def test_bootstrap_zero_iterations() -> None:
    """num_bootstraps=0 collapses CI bounds to the point estimate."""
    matrix = [["A", "A"], ["B", "B"], ["A", "B"]] * 5
    res = compute_agreement(matrix, num_bootstraps=0)
    assert res.ci_lower == res.krippendorff_alpha
    assert res.ci_upper == res.krippendorff_alpha
    assert res.num_bootstraps == 0


def test_measure_contract_and_alias() -> None:
    """measure(labels_a, labels_b) behaves identically to compute_agreement."""
    a = ["A", "B", "A", "B", "C"] * 4
    b = ["A", "B", "B", "B", "C"] * 4

    res_measure = measure(a, b, num_bootstraps=100, seed=2027)
    res_matrix = compute_agreement(list(zip(a, b)), num_bootstraps=100, seed=2027)

    assert isinstance(res_measure, Agreement)
    assert res_measure.krippendorff_alpha == res_matrix.krippendorff_alpha
    assert res_measure.cohen_kappa == res_matrix.cohen_kappa
    assert res_measure.ci_lower == res_matrix.ci_lower
    assert res_measure.ci_upper == res_matrix.ci_upper


def test_json_serializability() -> None:
    """AgreementResult serializes to valid JSON via to_dict()."""
    matrix = [["A", "A"], ["B", "B"]] * 5
    res = compute_agreement(matrix, num_bootstraps=50, seed=2027)
    payload = res.to_dict()

    serialized = json.dumps(payload)
    deserialized = json.loads(serialized)

    assert deserialized["krippendorff_alpha"] == pytest.approx(1.0)
    assert deserialized["cohen_kappa"] == pytest.approx(1.0)
    assert deserialized["reason_code"] == "OK"
    assert "version" in deserialized


# ==============================================================================
# Adversarial Controls
# ==============================================================================


def test_empty_ratings_matrix_refused() -> None:
    """Empty ratings matrices are refused with EMPTY_RATINGS_MATRIX."""
    for empty in [[], [[]], [[], []]]:
        with pytest.raises(RaterAgreementError) as exc_info:
            compute_agreement(empty)
        assert exc_info.value.reason_code == "EMPTY_RATINGS_MATRIX"


def test_insufficient_raters_refused() -> None:
    """Ratings matrices with fewer than 2 raters are refused with INSUFFICIENT_RATERS."""
    single_column = [["VALID"], ["OVERREAD"], ["UNDERREAD"]]
    with pytest.raises(RaterAgreementError) as exc_info:
        compute_agreement(single_column)
    assert exc_info.value.reason_code == "INSUFFICIENT_RATERS"


def test_no_pairable_units_refused() -> None:
    """Matrix where no unit has at least 2 non-missing ratings raises NO_PAIRABLE_UNITS."""
    unpairable = [
        ["A", None],
        [None, "B"],
        ["", "C"],
        [float("nan"), None],
    ]
    with pytest.raises(RaterAgreementError) as exc_info:
        compute_agreement(unpairable)
    assert exc_info.value.reason_code == "NO_PAIRABLE_UNITS"


def test_all_disagreement_two_raters() -> None:
    """All-disagreement across 2 raters computes non-positive alpha/kappa without NaN."""
    matrix = [
        ["A", "B"],
        ["B", "A"],
        ["A", "B"],
        ["B", "A"],
    ] * 5
    res = compute_agreement(matrix, num_bootstraps=100, seed=2027)

    assert res.krippendorff_alpha <= 0.0
    assert not math.isnan(res.krippendorff_alpha)
    assert res.cohen_kappa is not None
    assert res.cohen_kappa <= 0.0
    assert not math.isnan(res.cohen_kappa)
    assert not math.isnan(res.ci_lower)
    assert not math.isnan(res.ci_upper)


def test_all_disagreement_three_raters() -> None:
    """All-disagreement across 3 raters computes non-positive alpha without NaN."""
    matrix = [
        ["A", "B", "C"],
        ["B", "C", "A"],
        ["C", "A", "B"],
    ] * 5
    res = compute_agreement(matrix, num_bootstraps=100, seed=2027)

    assert res.krippendorff_alpha <= 0.0
    assert not math.isnan(res.krippendorff_alpha)
    assert res.cohen_kappa is None
    assert not math.isnan(res.ci_lower)
    assert not math.isnan(res.ci_upper)


def test_missing_labels_handled_without_nan_crash() -> None:
    """Missing labels (None, empty string, NaN) are safely skipped without crash or NaN."""
    matrix = [
        ["VALID", "VALID", None],
        ["OVERREAD", None, "OVERREAD"],
        [float("nan"), "UNDERREAD", "UNDERREAD"],
        ["INDETERMINATE", "INDETERMINATE", "INDETERMINATE"],
        ["VALID", None, None],  # only 1 rating, should be skipped for pairs
        [None, "", float("nan")],  # all missing, should be skipped
        ["", "OVERREAD", None],  # only 1 rating, should be skipped
        ["UNDERREAD", "UNDERREAD", ""],
    ] * 4

    res = compute_agreement(matrix, num_bootstraps=150, seed=2027)

    # All pairable units in this matrix have perfect consensus
    assert res.krippendorff_alpha == pytest.approx(1.0)
    assert not math.isnan(res.krippendorff_alpha)
    assert not math.isnan(res.ci_lower)
    assert not math.isnan(res.ci_upper)
    assert res.ci_lower == pytest.approx(1.0)
    assert res.ci_upper == pytest.approx(1.0)


def test_invalid_parameters_fail_closed() -> None:
    """Invalid bootstrap parameters or mismatched sequence lengths fail closed."""
    valid_matrix = [["A", "A"], ["B", "B"]]

    with pytest.raises(RaterAgreementError) as exc_boot:
        compute_agreement(valid_matrix, num_bootstraps=-1)
    assert exc_boot.value.reason_code == "INVALID_BOOTSTRAP_PARAMS"

    with pytest.raises(RaterAgreementError) as exc_conf:
        compute_agreement(valid_matrix, confidence_level=1.2)
    assert exc_conf.value.reason_code == "INVALID_BOOTSTRAP_PARAMS"

    with pytest.raises(RaterAgreementError) as exc_len:
        measure(["A", "B"], ["A"])
    assert exc_len.value.reason_code == "MISMATCHED_LENGTHS"

    with pytest.raises(RaterAgreementError) as exc_row:
        compute_agreement([1, 2, 3])  # type: ignore[arg-type]
    assert exc_row.value.reason_code == "INVALID_RATINGS_MATRIX"
