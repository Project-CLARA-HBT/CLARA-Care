"""Tests for AIME-runner (Phase P05, venue ``aime``) — uniform arm execution runner.

Purpose
-------
Unit, integration and adversarial contract tests for
:mod:`evaluation.venue2027.aime.runner`
(``research/venue2027/VENUES/aime/TASKS/AIME-runner.md``).

Positive controls (must pass):
- Every planned arm x vignette pair is recorded in the denominator; nothing
  is ever silently dropped (denominator completeness).
- Deterministic replay: same config produces identical pair digests and identical
  JSONL output.
- All default baseline arms (B0-B5) and candidate C0 are supported.
- Resumable journal: idempotent execution against an existing journal file
  performs zero new adapter calls.
- Bundle passes the repository-wide measurement standard
  (:func:`evaluation.venue2027._shared.measurement.assert_denominator_consistency`).

Adversarial controls (must be refused / recorded, never dropped):
- An arm that raises/crashes is recorded as ``EXECUTION_ERROR`` with its
  exception class and is NOT dropped from the denominator.
- Unequal configuration across arms is strictly refused (``UNEQUAL_CONFIG_REFUSED``):
  seed drift, differing timeouts, or differing model/prompt configurations.
- Provider-dependent arms without an active provider yield ``NOT_RUN_EXTERNAL``
  (never a fake pass, safe rejection, or completion).
- Malformed configuration (empty campaign/arms, duplicate IDs, invalid source SHA,
  non-positive timeout, invalid workers, unknown arm) fails closed with stable
  reason codes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.venue2027._shared import measurement as M
from evaluation.venue2027._shared.harness import (
    OUTCOME_BUCKETS,
    RunBundle,
)
from evaluation.venue2027.aime.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINE_B4,
    BASELINE_B5,
    REASON_PROVIDER_DEPENDENT,
)
from evaluation.venue2027.aime.candidate import CANDIDATE_ARM_ID
from evaluation.venue2027.aime.runner import (
    CampaignConfig,
    RunnerError,
    generate_synthetic_vignettes,
    run_campaign,
)

SHA40 = "28ff55110f980f42002524cef126290e91258cd6"


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_every_arm_x_vignette_pair_recorded_and_complete() -> None:
    """Every planned arm x vignette pair is accounted for in the denominator."""
    cfg = CampaignConfig(
        campaign_id="test-positive-full",
        arm_ids=(BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3, BASELINE_B4, BASELINE_B5),
        seed=2027,
        source_commit=SHA40,
        n_vignettes=5,
    )
    bundle = run_campaign(cfg)

    assert isinstance(bundle, RunBundle)
    planned = len(cfg.arm_ids) * 5
    assert bundle.manifest["planned_pairs"] == planned
    assert bundle.manifest["attempted_pairs"] == planned
    assert bundle.manifest["missing_pairs"] == 0
    assert bundle.manifest["complete"] is True
    assert len(bundle.records) == planned

    # Verify every (arm_id, case_id) pair was recorded exactly once
    observed_pairs = [(r["arm_id"], r["case_id"]) for r in bundle.records]
    assert len(set(observed_pairs)) == planned

    # Verify mutually exclusive counts partition the total
    counts = bundle.outcome_counts()
    assert sum(counts.values()) == planned
    for bucket in OUTCOME_BUCKETS:
        assert bucket.lower() in counts

    # Verify per-record fields
    for r in bundle.records:
        assert r["record_kind"] == "pair_result"
        assert len(r["pair_digest"]) == 64
        assert r["source_commit"] == SHA40
        assert r["seed"] == 2027
        assert r["oracle"]["oracle_id"] == "aime-clinical-reference"
        assert r["oracle"]["expected_outcome"] in ("ADMIT", "REJECT", "INDETERMINATE")


def test_positive_deterministic_execution_identical_replay() -> None:
    """Same campaign config produces identical records, digests and outcomes."""
    cfg = CampaignConfig(
        campaign_id="test-determinism",
        arm_ids=(BASELINE_B0, BASELINE_B4),
        seed=42,
        source_commit=SHA40,
        n_vignettes=3,
    )
    run1 = run_campaign(cfg)
    run2 = run_campaign(cfg)

    assert [r["pair_digest"] for r in run1.records] == [r["pair_digest"] for r in run2.records]
    assert run1.outcome_counts() == run2.outcome_counts()
    for r1, r2 in zip(run1.records, run2.records):
        assert r1["pair_digest"] == r2["pair_digest"]
        assert r1["outcome"] == r2["outcome"]
        assert r1["oracle"] == r2["oracle"]
        assert r1["arm_id"] == r2["arm_id"]
        assert r1["case_id"] == r2["case_id"]


def test_positive_candidate_arm_c0_execution() -> None:
    """Candidate C0 algorithm executes cleanly through the runner."""
    cfg = CampaignConfig(
        campaign_id="test-candidate-c0",
        arm_ids=(CANDIDATE_ARM_ID,),
        seed=2027,
        source_commit=SHA40,
        n_vignettes=5,
    )
    bundle = run_campaign(cfg)
    assert len(bundle.records) == 5
    for r in bundle.records:
        assert r["arm_id"] == CANDIDATE_ARM_ID
        assert r["outcome"]["observed_outcome"] in ("ADMIT", "REJECT", "INDETERMINATE")


def test_positive_measurement_denominator_consistency() -> None:
    """Run bundle passes program-level assert_denominator_consistency."""
    bundle = run_campaign({"n_vignettes": 5, "seed": 2027, "source_commit": SHA40})
    counts = M.assert_denominator_consistency(bundle)
    assert sum(counts.values()) == 30
    assert counts["admit"] > 0
    assert counts["reject"] > 0
    assert counts["indeterminate"] > 0
    assert counts["not_run"] > 0


def test_positive_resumable_journal_idempotency(tmp_path: Path) -> None:
    """Interrupted execution can resume via journal; duplicate calls are zero."""
    journal_file = tmp_path / "campaign_journal.jsonl"
    cfg = CampaignConfig(
        campaign_id="test-resumption",
        arm_ids=(BASELINE_B0, BASELINE_B1),
        seed=100,
        source_commit=SHA40,
        n_vignettes=3,
        journal_path=journal_file,
    )

    # Initial run writes journal
    run1 = run_campaign(cfg)
    assert run1.manifest["executed_pairs"] == 6
    assert run1.manifest["resumed_pairs"] == 0
    assert journal_file.is_file()

    # Second run against same journal performs 0 adapter executions
    run2 = run_campaign(cfg)
    assert run2.manifest["executed_pairs"] == 0
    assert run2.manifest["resumed_pairs"] == 6
    assert [r["pair_digest"] for r in run1.records] == [r["pair_digest"] for r in run2.records]
    assert run1.outcome_counts() == run2.outcome_counts()


def test_positive_synthetic_vignettes_generation() -> None:
    """generate_synthetic_vignettes balances the 5 AIME update families with no PHI."""
    vignettes = generate_synthetic_vignettes(n=10, seed=777)
    assert len(vignettes) == 10
    families = [v["family"] for v in vignettes]
    for fam in (
        "stable_history",
        "consent_change",
        "medication_withdrawal",
        "allergy_update",
        "reconciliation",
    ):
        assert families.count(fam) == 2
    for v in vignettes:
        assert v["synthetic_only"] is True
        assert "snapshot" in v
        assert "current" in v
        assert "timeline" in v
        assert "task" in v
        # Ensure no PHI markers exist
        for phi in ("name", "email", "mrn", "patient_name", "phone"):
            assert phi not in v


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_crashing_arm_recorded_as_execution_error_not_dropped() -> None:
    """An arm that raises/crashes is recorded as EXECUTION_ERROR and never dropped."""

    def exploding_arm(_case, _ctx):
        raise RuntimeError("Simulated adapter catastrophe")

    cfg = CampaignConfig(
        campaign_id="test-crashing-arm",
        arm_ids=("exploding_arm", BASELINE_B0),
        seed=2027,
        source_commit=SHA40,
        n_vignettes=3,
        custom_adapters={"exploding_arm": exploding_arm},
    )
    bundle = run_campaign(cfg)

    # Denominator completeness: 2 arms * 3 cases = 6 pairs planned & attempted
    assert bundle.manifest["planned_pairs"] == 6
    assert bundle.manifest["attempted_pairs"] == 6
    assert bundle.manifest["missing_pairs"] == 0
    assert bundle.manifest["complete"] is True

    crash_records = [r for r in bundle.records if r["arm_id"] == "exploding_arm"]
    assert len(crash_records) == 3
    for r in crash_records:
        assert r["outcome"]["observed_outcome"] == "EXECUTION_ERROR"
        assert r["outcome"]["counted_as_success"] is False
        assert "RuntimeError" in r["outcome"]["detail"]

    ok_records = [r for r in bundle.records if r["arm_id"] == BASELINE_B0]
    assert len(ok_records) == 3
    for r in ok_records:
        assert r["outcome"]["observed_outcome"] == "ADMIT"

    assert bundle.manifest["denominator"]["execution_error"] == 3


def test_adversarial_unequal_config_seed_drift_refused() -> None:
    """Unequal seeds across arms are strictly refused before execution."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            {
                "arm_ids": (BASELINE_B0, BASELINE_B1),
                "seeds": (2027, 2028),
                "source_commit": SHA40,
                "n_vignettes": 2,
            }
        )
    assert exc_info.value.reason_code == "UNEQUAL_CONFIG_REFUSED"


def test_adversarial_unequal_config_arm_configs_refused() -> None:
    """Differing arm configurations (model, prompt, temperature, timeout) are refused."""
    # Differing models across arms
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            {
                "arm_ids": (BASELINE_B0, BASELINE_B1),
                "seed": 2027,
                "source_commit": SHA40,
                "arm_configs": {
                    BASELINE_B0: {"model": "model-pro", "temperature": 0.0},
                    BASELINE_B1: {"model": "model-flash", "temperature": 0.0},
                },
                "n_vignettes": 2,
            }
        )
    assert exc_info.value.reason_code == "UNEQUAL_CONFIG_REFUSED"

    # Differing timeouts across arms
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            {
                "arm_ids": (BASELINE_B0, BASELINE_B1),
                "seed": 2027,
                "source_commit": SHA40,
                "arm_configs": {
                    BASELINE_B0: {"timeout": 30.0},
                    BASELINE_B1: {"timeout": 60.0},
                },
                "n_vignettes": 2,
            }
        )
    assert exc_info.value.reason_code == "UNEQUAL_CONFIG_REFUSED"

    # Missing arm configuration entry
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            {
                "arm_ids": (BASELINE_B0, BASELINE_B1),
                "seed": 2027,
                "source_commit": SHA40,
                "arm_configs": {
                    BASELINE_B0: {"model": "study-pinned"},
                },
                "n_vignettes": 2,
            }
        )
    assert exc_info.value.reason_code == "UNEQUAL_CONFIG_REFUSED"


def test_adversarial_provider_dependent_arm_without_provider_yields_not_run_external() -> None:
    """Provider-dependent arm (B2) without an active provider yields NOT_RUN_EXTERNAL, never a fake result."""
    cfg = CampaignConfig(
        campaign_id="test-provider-dependent",
        arm_ids=(BASELINE_B2,),
        seed=2027,
        source_commit=SHA40,
        n_vignettes=4,
        has_live_provider=False,
    )
    bundle = run_campaign(cfg)
    assert len(bundle.records) == 4
    for r in bundle.records:
        assert r["arm_id"] == BASELINE_B2
        outcome = r["outcome"]
        assert outcome["observed_outcome"] == "NOT_RUN_EXTERNAL"
        assert outcome["counted_as_success"] is False
        assert REASON_PROVIDER_DEPENDENT in outcome["detail"]

    # Declared provider-dependent arm via config
    cfg_custom = CampaignConfig(
        campaign_id="test-custom-provider-dep",
        arm_ids=("custom_llm_arm",),
        seed=2027,
        source_commit=SHA40,
        n_vignettes=2,
        provider_dependent_arms=("custom_llm_arm",),
        has_live_provider=False,
    )
    bundle_custom = run_campaign(cfg_custom)
    for r in bundle_custom.records:
        assert r["outcome"]["observed_outcome"] == "NOT_RUN_EXTERNAL"
        assert r["outcome"]["counted_as_success"] is False
        assert REASON_PROVIDER_DEPENDENT in r["outcome"]["detail"]


def test_adversarial_empty_scope_refused() -> None:
    """Empty campaign_id, empty arm_ids, or empty vignettes fail closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"campaign_id": "", "source_commit": SHA40})
    assert exc_info.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"arm_ids": (), "source_commit": SHA40})
    assert exc_info.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"vignettes": (), "source_commit": SHA40})
    assert exc_info.value.reason_code == "EMPTY_SCOPE"


def test_adversarial_duplicate_arm_ids_refused() -> None:
    """Duplicate arm_ids fail closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"arm_ids": (BASELINE_B0, BASELINE_B0), "source_commit": SHA40})
    assert exc_info.value.reason_code == "DUPLICATE_ID"


def test_adversarial_invalid_source_sha_refused() -> None:
    """Non-40-hex source SHA fails closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"source_commit": "not-a-40-hex-sha"})
    assert exc_info.value.reason_code == "MISSING_SOURCE_SHA"


def test_adversarial_invalid_timeout_and_workers_refused() -> None:
    """Non-positive timeout or workers < 1 fail closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"per_pair_timeout_seconds": -1.0, "source_commit": SHA40})
    assert exc_info.value.reason_code == "INVALID_TIMEOUT"

    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"workers": 0, "source_commit": SHA40})
    assert exc_info.value.reason_code == "INVALID_WORKERS"


def test_adversarial_unknown_arm_refused() -> None:
    """Unregistered arm without an injected adapter fails closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign({"arm_ids": ("B99-unknown-mythical-arm",), "source_commit": SHA40})
    assert exc_info.value.reason_code == "UNKNOWN_ARM"
