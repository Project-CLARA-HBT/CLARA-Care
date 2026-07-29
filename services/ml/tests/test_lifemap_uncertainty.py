import pytest

from clara_ml.lifemap.uncertainty import (
    SufficiencyPolicy,
    UncertaintyError,
    assess_uncertainty,
    ensemble_disagreement,
    expected_calibration_error,
    split_conformal_interval,
    standardized_ood_score,
)


def test_calibration_and_ensemble_metrics_are_task_specific() -> None:
    assert expected_calibration_error((0.1, 0.2, 0.8, 0.9), (0, 0, 1, 1)) < 0.2
    assert ensemble_disagreement((1.0, 2.0, 3.0)) > 0
    assert standardized_ood_score((10.0, 0.0), (0.0, 0.0), (1.0, 1.0)) > 5


def test_conformal_output_fails_when_exchangeability_or_shift_gate_fails() -> None:
    with pytest.raises(UncertaintyError, match="assumptions_not_met"):
        split_conformal_interval(
            point=10,
            calibration_residuals=(1, 2, 3),
            alpha=0.1,
            exchangeability_approved=True,
            shift_detected=True,
        )
    assert split_conformal_interval(
        point=10,
        calibration_residuals=(1, 2, 3, 4),
        alpha=0.25,
        exchangeability_approved=True,
        shift_detected=False,
    ) == (6, 14)


def test_insufficient_ood_invalid_calibration_or_revocation_abstains() -> None:
    result = assess_uncertainty(
        sample_count=3,
        coverage=0.2,
        missing_fraction=0.8,
        sufficiency=SufficiencyPolicy(10, 0.8, 0.2),
        release_state="champion",
        calibration_valid=False,
        uncertainty_within_boundary=True,
        ood_score=4,
        ood_threshold=3,
        source_revoked=True,
    )
    assert result.decision == "abstain"
    assert set(result.reasons) == {
        "source_revoked",
        "insufficient_data",
        "out_of_distribution",
        "calibration_invalid",
    }


def test_shadow_never_releases_and_pilot_requires_uncertainty_boundary() -> None:
    kwargs = {
        "sample_count": 20,
        "coverage": 1.0,
        "missing_fraction": 0.0,
        "sufficiency": SufficiencyPolicy(10, 0.8, 0.2),
        "calibration_valid": True,
        "ood_score": 1.0,
        "ood_threshold": 3.0,
    }
    assert (
        assess_uncertainty(
            **kwargs,
            release_state="shadow",
            uncertainty_within_boundary=True,
        ).decision
        == "private_shadow"
    )
    assert (
        assess_uncertainty(
            **kwargs,
            release_state="pilot",
            uncertainty_within_boundary=False,
        ).decision
        == "needs_review"
    )
