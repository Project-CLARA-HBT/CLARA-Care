"""ACNS-X06_adjudication — Compute independent coder agreement.

Purpose
-------
Task ACNS-X06_adjudication (Phase P05, venue acns; SoK: Evidence Boundaries of
Attestation in Tool-Using AI Systems) implements inter-rater agreement measurement
for nominal classifications across independent raters.

This module provides:
- Krippendorff's alpha reliability metric for nominal data supporting multiple
  raters and missing/unbalanced observations.
- Cross-check with Cohen's kappa when complete pairs across two raters are present.
- Case/paper clustered non-parametric bootstrap confidence intervals with a
  deterministic random seed.
- Pure standard library implementation without external statistics dependencies.

Allowed input
-------------
- ``ratings_matrix``: A 2D sequence of ratings (rows = units/cases/papers,
  columns = raters). Cells may be categorical labels (str, int, bool) or missing
  values (``None``, empty string ``""``, or ``float("nan")``).
- ``labels_a``, ``labels_b``: Sequences of ratings from two raters for ``measure``.
- ``num_bootstraps``: Integer number of bootstrap iterations (>= 0, default 1000).
- ``seed``: Integer seed for deterministic bootstrap sampling (default 2027).
- ``confidence_level``: Two-sided confidence level in (0, 1) (default 0.95).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes on invalid inputs:
- ``EMPTY_RATINGS_MATRIX`` — empty ratings matrix or all rows empty.
- ``INSUFFICIENT_RATERS`` — fewer than 2 raters/columns.
- ``NO_PAIRABLE_UNITS`` — no units have at least 2 non-missing ratings.
- ``INSUFFICIENT_DATA`` — total pairable ratings count is less than 2.
- ``MISMATCHED_LENGTHS`` — paired input lists have unequal lengths.
- ``INVALID_RATINGS_MATRIX`` — rows are not sequences or ill-formed.
- ``INVALID_BOOTSTRAP_PARAMS`` — invalid bootstrap count or confidence level.

Version
-------
RATER_AGREEMENT_VERSION = "1.0.0"
"""

from __future__ import annotations

import collections
import dataclasses
import math
import random
from collections.abc import Sequence
from typing import Any

RATER_AGREEMENT_VERSION = "1.0.0"


class RaterAgreementError(ValueError):
    """Domain exception for rater agreement calculation failure."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code
        self.message = message


@dataclasses.dataclass(frozen=True)
class AgreementResult:
    """Inter-rater agreement evaluation summary."""

    krippendorff_alpha: float
    cohen_kappa: float | None
    ci_lower: float
    ci_upper: float
    num_units: int = 0
    num_raters: int = 0
    num_bootstraps: int = 1000
    confidence_level: float = 0.95
    reason_code: str = "OK"

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a plain JSON-compatible dictionary."""
        return {
            "krippendorff_alpha": self.krippendorff_alpha,
            "cohen_kappa": self.cohen_kappa,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "num_units": self.num_units,
            "num_raters": self.num_raters,
            "num_bootstraps": self.num_bootstraps,
            "confidence_level": self.confidence_level,
            "reason_code": self.reason_code,
            "version": RATER_AGREEMENT_VERSION,
        }


# Target contract alias
Agreement = AgreementResult


def _is_missing(val: Any) -> bool:
    """Check whether a cell value represents a missing rating."""
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _krippendorff_alpha_nominal(
    pairable_units: Sequence[collections.Counter[Any]],
) -> float:
    """Compute nominal Krippendorff's alpha from pre-filtered pairable units.

    Each unit in ``pairable_units`` is a Counter of non-missing labels with
    m_u >= 2.
    """
    if not pairable_units:
        raise RaterAgreementError(
            "NO_PAIRABLE_UNITS",
            "No units have at least 2 non-missing ratings to compute agreement.",
        )

    total_pairable_ratings = 0
    sum_coincidence_diag = 0.0
    global_counts: collections.Counter[Any] = collections.Counter()

    for unit_counts in pairable_units:
        m_u = sum(unit_counts.values())
        total_pairable_ratings += m_u
        global_counts.update(unit_counts)

        # Within-unit coincidence diagonal: sum_c (n_uc * (n_uc - 1)) / (m_u - 1)
        denom = m_u - 1
        unit_diag = sum(cnt * (cnt - 1) for cnt in unit_counts.values())
        sum_coincidence_diag += unit_diag / denom

    n = total_pairable_ratings
    if n <= 1:
        raise RaterAgreementError(
            "INSUFFICIENT_DATA",
            f"Total pairable ratings count ({n}) must be at least 2.",
        )

    # Observed disagreement Do = 1 - (sum_c o_cc / n)
    d_o = 1.0 - (sum_coincidence_diag / n)

    # Expected disagreement De = 1 - sum_c (n_c * (n_c - 1)) / (n * (n - 1))
    expected_agreement_num = sum(cnt * (cnt - 1) for cnt in global_counts.values())
    expected_agreement_denom = n * (n - 1)
    d_e = 1.0 - (expected_agreement_num / expected_agreement_denom)

    # Clean zero-variance or near-zero edge conditions
    if abs(d_e) < 1e-12:
        return 1.0 if abs(d_o) < 1e-12 else 0.0

    if abs(d_o) < 1e-12:
        return 1.0

    alpha = 1.0 - (d_o / d_e)
    return float(alpha)


def _compute_cohen_kappa(pairs: Sequence[tuple[Any, Any]]) -> float | None:
    """Compute Cohen's kappa for two raters across complete pairs."""
    n = len(pairs)
    if n == 0:
        return None

    observed_agreements = sum(1 for a, b in pairs if a == b)
    p_o = observed_agreements / n

    left_counts = collections.Counter(a for a, _ in pairs)
    right_counts = collections.Counter(b for _, b in pairs)
    categories = set(left_counts) | set(right_counts)

    p_e = sum((left_counts[c] / n) * (right_counts[c] / n) for c in categories)

    if p_e >= 1.0 - 1e-12:
        return 1.0 if abs(p_o - 1.0) < 1e-12 else 0.0

    kappa = (p_o - p_e) / (1.0 - p_e)
    return float(kappa)


def compute_agreement(
    ratings_matrix: Sequence[Sequence[Any]],
    num_bootstraps: int = 1000,
    seed: int = 2027,
    confidence_level: float = 0.95,
) -> AgreementResult:
    """Compute Krippendorff alpha, Cohen kappa (if complete pairs), and bootstrap CI.

    Parameters
    ----------
    ratings_matrix : Sequence[Sequence[Any]]
        2D sequence where each row is an independent unit (paper/case) and each
        column is a rater's rating. Missing labels may be None, "", or NaN.
    num_bootstraps : int, optional
        Number of resamples for percentile bootstrap (default 1000). If 0, CI bounds
        match the point estimate.
    seed : int, optional
        Deterministic random seed for the bootstrap procedure (default 2027).
    confidence_level : float, optional
        Confidence level for two-sided percentile confidence interval (default 0.95).

    Returns
    -------
    AgreementResult
        Result containing krippendorff_alpha, cohen_kappa, ci_lower, and ci_upper.
    """
    if num_bootstraps < 0:
        raise RaterAgreementError(
            "INVALID_BOOTSTRAP_PARAMS",
            f"num_bootstraps must be non-negative, got {num_bootstraps}.",
        )
    if not (0.0 < confidence_level < 1.0):
        raise RaterAgreementError(
            "INVALID_BOOTSTRAP_PARAMS",
            f"confidence_level must be in (0, 1), got {confidence_level}.",
        )

    if not isinstance(ratings_matrix, Sequence) or len(ratings_matrix) == 0:
        raise RaterAgreementError(
            "EMPTY_RATINGS_MATRIX",
            "Ratings matrix is empty or not a valid sequence.",
        )

    rows: list[list[Any]] = []
    for row in ratings_matrix:
        if not isinstance(row, Sequence):
            raise RaterAgreementError(
                "INVALID_RATINGS_MATRIX",
                f"Each row in ratings_matrix must be a Sequence, got {type(row).__name__}.",
            )
        rows.append(list(row))

    num_units = len(rows)
    if all(len(r) == 0 for r in rows):
        raise RaterAgreementError(
            "EMPTY_RATINGS_MATRIX",
            "Ratings matrix contains only empty rows.",
        )

    num_raters = max(len(r) for r in rows) if rows else 0
    if num_raters < 2:
        raise RaterAgreementError(
            "INSUFFICIENT_RATERS",
            f"Ratings matrix must have at least 2 raters/columns, found {num_raters}.",
        )

    # Collect pairable units for point estimate
    pairable_units: list[collections.Counter[Any]] = []
    for r in rows:
        valid = [v for v in r if not _is_missing(v)]
        if len(valid) >= 2:
            pairable_units.append(collections.Counter(valid))

    if not pairable_units:
        raise RaterAgreementError(
            "NO_PAIRABLE_UNITS",
            "No units have at least 2 non-missing ratings.",
        )

    krippendorff_alpha = _krippendorff_alpha_nominal(pairable_units)

    # Cross-check simple Cohen's kappa if exactly 2 raters and complete pairs exist
    cohen_kappa: float | None = None
    all_rows_equal_len = all(len(r) == num_raters for r in rows)
    if num_raters == 2 and all_rows_equal_len:
        complete_pairs: list[tuple[Any, Any]] = []
        for r in rows:
            if len(r) >= 2 and not _is_missing(r[0]) and not _is_missing(r[1]):
                complete_pairs.append((r[0], r[1]))
        if complete_pairs:
            cohen_kappa = _compute_cohen_kappa(complete_pairs)

    # Clustered bootstrap by paper/case (rows)
    if num_bootstraps == 0:
        ci_lower = krippendorff_alpha
        ci_upper = krippendorff_alpha
    else:
        rng = random.Random(seed)
        boot_alphas: list[float] = []

        for _ in range(num_bootstraps):
            # Resample N units with replacement
            sample_rows = [rows[rng.randrange(num_units)] for _ in range(num_units)]
            sample_pairable: list[collections.Counter[Any]] = []
            for r in sample_rows:
                valid = [v for v in r if not _is_missing(v)]
                if len(valid) >= 2:
                    sample_pairable.append(collections.Counter(valid))

            if not sample_pairable:
                boot_alphas.append(krippendorff_alpha)
                continue

            try:
                alpha_b = _krippendorff_alpha_nominal(sample_pairable)
                boot_alphas.append(alpha_b)
            except RaterAgreementError:
                boot_alphas.append(krippendorff_alpha)

        boot_alphas.sort()
        alpha_half = (1.0 - confidence_level) / 2.0
        lower_idx = int(round(alpha_half * (num_bootstraps - 1)))
        upper_idx = int(round((1.0 - alpha_half) * (num_bootstraps - 1)))
        lower_idx = max(0, min(num_bootstraps - 1, lower_idx))
        upper_idx = max(0, min(num_bootstraps - 1, upper_idx))
        ci_lower = float(boot_alphas[lower_idx])
        ci_upper = float(boot_alphas[upper_idx])

    return AgreementResult(
        krippendorff_alpha=krippendorff_alpha,
        cohen_kappa=cohen_kappa,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        num_units=num_units,
        num_raters=num_raters,
        num_bootstraps=num_bootstraps,
        confidence_level=confidence_level,
        reason_code="OK",
    )


def measure(
    labels_a: Sequence[Any],
    labels_b: Sequence[Any],
    num_bootstraps: int = 1000,
    seed: int = 2027,
    confidence_level: float = 0.95,
) -> AgreementResult:
    """Compute agreement between two raters' label sequences.

    Convenience wrapper that constructs a 2-column ratings matrix and delegates
    to ``compute_agreement``.
    """
    if len(labels_a) != len(labels_b):
        raise RaterAgreementError(
            "MISMATCHED_LENGTHS",
            f"Length of labels_a ({len(labels_a)}) must match labels_b ({len(labels_b)}).",
        )
    ratings_matrix = list(zip(labels_a, labels_b))
    return compute_agreement(
        ratings_matrix=ratings_matrix,
        num_bootstraps=num_bootstraps,
        seed=seed,
        confidence_level=confidence_level,
    )
