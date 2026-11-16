"""Tests for POPETS-pilot (development split pilot executor).

Positive controls (must pass):
- Pilot runs cleanly on development split (split: dev), leaves test split untouched.
- Measures empirical runtime distribution (mean, variance, p95) and full denominator.
- Computes empirical outcome variance and paired difference variance.
- Calculates prospective power estimates and Clopper-Pearson zero-event bounds.
- Baseline fairness and balanced pairing parity confirmed across all arms.
- Candidate arm B4 achieves zero oracle disagreements on development cases.
- Loads and adheres to protocol/pilot_plan.yaml.
- Exact target contract pilot(config) -> PilotReport functions identically.

Adversarial controls (must fail closed):
- Attempting to run on test split in config is refused with HOLDOUT_ACCESS_FORBIDDEN.
- Attempting to run on holdout split in config is refused with HOLDOUT_ACCESS_FORBIDDEN.
- Passing a test split Dataset object is refused with HOLDOUT_ACCESS_FORBIDDEN.
- Passing cases/records with split='test' or split='holdout' is refused with HOLDOUT_ACCESS_FORBIDDEN.
- Empty dev split / empty scope is refused with EMPTY_SCOPE.
- Malformed configuration types are refused with CONFIG_MALFORMED.
- Unequal arm configurations are refused with UNEQUAL_ARM_CONFIG.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from evaluation.venue2027.popets.generate_dataset import generate
from evaluation.venue2027.popets.pilot_executor import (
    DEFAULT_FEASIBLE_SEEDS,
    FeasibleMatrix,
    PilotConfig,
    PilotError,
    PilotReport,
    PowerEstimates,
    RuntimeStats,
    VarianceEstimates,
    execute_pilot,
    load_pilot_plan,
    pilot,
)
from evaluation.venue2027.popets.runner import CampaignConfig, RunnerError, run_campaign

FIXED_SEED = 42
PILOT_N = 20


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_pilot_runs_on_dev_split_and_computes_variance() -> None:
    """Pilot executes strictly on dev split, computes variance, leaves test untouched."""
    config = PilotConfig(
        pilot_id="test-pilot-dev-positive",
        split="dev",
        seed=FIXED_SEED,
        n=PILOT_N,
    )
    report = execute_pilot(config)

    assert isinstance(report, PilotReport)
    assert report.split == "dev"
    assert report.holdout_untouched is True
    assert report.n_cases == 4  # 20% of 20 = 4 dev records
    assert report.complete is True
    assert report.planned_pairs == len(report.arm_ids) * report.n_cases
    assert report.attempted_pairs == report.planned_pairs

    # Runtime statistics
    assert isinstance(report.runtime_stats, RuntimeStats)
    assert report.runtime_stats.total_wall_seconds >= 0.0
    assert report.runtime_stats.mean_pair_duration_seconds >= 0.0
    assert report.runtime_stats.variance_pair_duration >= 0.0
    assert report.runtime_stats.p95_pair_duration_seconds >= 0.0
    assert len(report.runtime_stats.per_arm_stats) == len(report.arm_ids)

    # Variance estimates
    assert isinstance(report.variance_estimates, VarianceEstimates)
    assert "B4" in report.variance_estimates.outcome_variance_by_arm
    assert report.variance_estimates.duration_variance >= 0.0
    assert isinstance(report.variance_estimates.paired_difference_variance, dict)

    # Power estimates and Clopper-Pearson bounds
    assert isinstance(report.power_estimates, PowerEstimates)
    assert report.power_estimates.alpha == 0.05
    assert report.power_estimates.target_power == 0.80
    assert "600" in report.power_estimates.clopper_pearson_bounds
    # N=600 gives Clopper-Pearson zero-event bound approx 0.0050
    assert report.power_estimates.clopper_pearson_bounds["600"] < 0.01
    assert "delta_0.15" in report.power_estimates.power_by_sample_size

    # Feasible matrix
    assert isinstance(report.feasible_matrix, FeasibleMatrix)
    assert report.feasible_matrix.seeds == DEFAULT_FEASIBLE_SEEDS
    assert report.feasible_matrix.holdout_untouched is True
    assert report.feasible_matrix.sample_sizes["confirmatory_study_n"] == 1200

    # JSON serialization
    serialized = report.to_dict()
    assert isinstance(serialized, dict)
    encoded = json.dumps(serialized)
    assert len(encoded) > 0


def test_pilot_target_contract_function() -> None:
    """Exact target signature pilot(config) -> PilotReport executes cleanly."""
    config = PilotConfig(
        pilot_id="test-pilot-contract-sig",
        split="dev",
        seed=FIXED_SEED,
        n=PILOT_N,
    )
    report = pilot(config)
    assert isinstance(report, PilotReport)
    assert report.split == "dev"
    assert report.holdout_untouched is True


def test_pilot_with_explicit_dev_dataset() -> None:
    """Passing a pre-generated dev dataset executes directly."""
    dev_ds = generate(seed=FIXED_SEED, split="dev", n=PILOT_N)
    config = PilotConfig(pilot_id="test-pilot-explicit-ds", seed=FIXED_SEED)
    report = execute_pilot(config, dev_dataset=dev_ds)

    assert report.split == "dev"
    assert report.n_cases == len(dev_ds.records)
    assert report.holdout_untouched is True


def test_pilot_plan_yaml_conforms_and_loads() -> None:
    """Loaded protocol/pilot_plan.yaml matches contract and executes dev pilot."""
    plan = load_pilot_plan()
    assert plan["schema_version"] == "clara.venue2027.popets.pilot_plan.v1"
    assert plan["split_policy"]["target_split"] == "dev"
    assert set(plan["split_policy"]["forbidden_splits"]) == {"test", "holdout"}
    assert plan["fairness_contract"]["balanced_pairing"] is True

    # Execute with plan parameters
    config = PilotConfig(
        pilot_id=plan["plan_id"] if "plan_id" in plan else "pilot-plan-run",
        split=plan["split_policy"]["target_split"],
        seed=plan["feasible_matrix"]["selected_seeds"][0],
        n=PILOT_N,
    )
    report = execute_pilot(config)
    assert report.split == "dev"
    assert report.holdout_untouched is True


def test_baseline_fairness_parity_enforced() -> None:
    """All arms are confirmed balanced under identical seed, timeouts, backends."""
    config = PilotConfig(pilot_id="test-fairness", seed=FIXED_SEED, n=PILOT_N)
    report = execute_pilot(config)

    fairness = report.baseline_fairness
    assert fairness["balanced_pairing"] is True
    assert fairness["enforce_equal_seeds"] is True
    assert fairness["enforce_equal_timeouts"] is True
    assert fairness["enforce_equal_retry_budgets"] is True
    assert fairness["enforce_equal_backends"] is True
    assert fairness["seed"] == FIXED_SEED


def test_candidate_arm_zero_oracle_disagreements() -> None:
    """Candidate arm B4 achieves 0 oracle disagreements on development cases."""
    config = PilotConfig(pilot_id="test-candidate-zero-disagreements", seed=FIXED_SEED, n=PILOT_N)
    report = execute_pilot(config)

    assert report.candidate_disagreements == 0


def test_power_monotonic_scaling() -> None:
    """Power estimates increase monotonically with sample size for all effect sizes."""
    config = PilotConfig(pilot_id="test-power-scaling", seed=FIXED_SEED, n=PILOT_N)
    report = execute_pilot(config)

    grid = report.power_estimates.power_by_sample_size
    for delta_key, sizes in grid.items():
        sample_sizes = sorted(int(k) for k in sizes.keys())
        powers = [sizes[str(s)] for s in sample_sizes]
        for i in range(len(powers) - 1):
            assert powers[i] <= powers[i + 1] + 1e-4, f"power dropped for {delta_key}: {powers}"


# ---------------------------------------------------------------------------
# Adversarial controls (must fail closed)
# ---------------------------------------------------------------------------


def test_refuse_test_split_in_config() -> None:
    """Attempting to configure split='test' is refused with HOLDOUT_ACCESS_FORBIDDEN."""
    config = PilotConfig(split="test")
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(config)
    assert exc_info.value.reason_code == "HOLDOUT_ACCESS_FORBIDDEN"


def test_refuse_holdout_split_in_config() -> None:
    """Attempting to configure split='holdout' is refused with HOLDOUT_ACCESS_FORBIDDEN."""
    config = PilotConfig(split="holdout")
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(config)
    assert exc_info.value.reason_code == "HOLDOUT_ACCESS_FORBIDDEN"


def test_refuse_test_dataset_object() -> None:
    """Passing a Dataset object of split='test' is refused with HOLDOUT_ACCESS_FORBIDDEN."""
    test_ds = generate(seed=FIXED_SEED, split="test", n=PILOT_N)
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(dev_dataset=test_ds)
    assert exc_info.value.reason_code == "HOLDOUT_ACCESS_FORBIDDEN"


def test_refuse_records_with_test_split() -> None:
    """Passing individual cases/records labeled with forbidden split is refused."""
    poisoned_records: list[dict[str, Any]] = [
        {"unit_id": "rev-poison-1", "family": "fresh", "split": "test", "payload": {}},
    ]
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(dev_dataset=poisoned_records)
    assert exc_info.value.reason_code == "HOLDOUT_ACCESS_FORBIDDEN"


def test_refuse_records_with_holdout_split() -> None:
    """Passing individual cases/records labeled with 'holdout' is refused."""
    poisoned_records: list[dict[str, Any]] = [
        {"unit_id": "rev-poison-2", "family": "fresh", "split": "holdout", "payload": {}},
    ]
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(dev_dataset=poisoned_records)
    assert exc_info.value.reason_code == "HOLDOUT_ACCESS_FORBIDDEN"


def test_refuse_empty_dataset() -> None:
    """Empty sequence of cases is refused with EMPTY_SCOPE."""
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(dev_dataset=[])
    assert exc_info.value.reason_code == "EMPTY_SCOPE"


def test_refuse_malformed_config() -> None:
    """Malformed configuration type is refused with CONFIG_MALFORMED."""
    with pytest.raises(PilotError) as exc_info:
        execute_pilot(config="invalid-config-type")  # type: ignore[arg-type]
    assert exc_info.value.reason_code == "CONFIG_MALFORMED"


def test_refuse_unequal_arm_config() -> None:
    """Unequal arm configurations (seed drift) are refused with UNEQUAL_ARM_CONFIG."""
    # Direct runner test of unequal arm config enforcement
    bad_cfg = CampaignConfig(
        campaign_id="test-seed-drift",
        arm_ids=("B1", "B2"),
        seed=FIXED_SEED,
        seeds=(FIXED_SEED, FIXED_SEED + 1),  # seed drift!
        cases=({"case_id": "c1"},),
    )
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(bad_cfg)
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"
