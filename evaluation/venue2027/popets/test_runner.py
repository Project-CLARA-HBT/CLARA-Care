"""Tests for POPETS-runner (uniform multi-arm execution runner).

Positive controls (must pass):
- All planned (arm x case) pairs are accounted for in the RunBundle, with
  mutually exclusive outcome buckets and full denominator coverage.
- Balanced pairing: every arm evaluates the exact same multiset of cases in
  identical order under the same seed, timeout, retry budget, and backend.
- Deterministic re-run: re-running with the same fixed seed produces identical
  pair digests and identical manifest outcome counts.
- Resumable journal: completed pairs are loaded from the journal; re-run
  performs zero duplicate executions (idempotent).
- Custom case sets and arm subsets execute cleanly.

Adversarial controls (must fail closed / record failures):
- An arm that crashes (raises an unhandled exception) is recorded as
  EXECUTION_ERROR with the exception class; it is NOT dropped from the
  denominator, and complete=True is preserved.
- Unequal arm configurations are refused before execution:
  - Seed drift between arms -> UNEQUAL_ARM_CONFIG
  - Unequal timeouts between arms -> UNEQUAL_ARM_CONFIG
  - Unequal retry budgets between arms -> UNEQUAL_ARM_CONFIG
  - Unequal execution backends between arms -> UNEQUAL_ARM_CONFIG
  - Unequal compiler or model versions between arms -> UNEQUAL_ARM_CONFIG
- Unknown arm identifiers without custom adapters -> UNKNOWN_ARM.
- Empty scopes (empty arms or cases) -> EMPTY_SCOPE.
- Malformed config types -> CONFIG_MALFORMED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.venue2027._shared.harness import OUTCOME_BUCKETS, Outcome, RunContext
from evaluation.venue2027.popets.privacy_cases import PRIVACY_CASE_IDS
from evaluation.venue2027.popets.runner import (
    DEFAULT_ARMS,
    CampaignConfig,
    RunnerError,
    run_campaign,
)

FIXED_SEED = 2027


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_all_arm_case_pairs_recorded_in_bundle() -> None:
    """Every planned arm x case pair is recorded with mutually exclusive outcomes."""
    config = CampaignConfig(
        campaign_id="test-all-pairs-recorded",
        seed=FIXED_SEED,
    )
    bundle = run_campaign(config)

    expected_pairs_count = len(DEFAULT_ARMS) * len(PRIVACY_CASE_IDS)
    manifest = bundle.manifest

    assert manifest["planned_pairs"] == expected_pairs_count
    assert manifest["attempted_pairs"] == expected_pairs_count
    assert manifest["missing_pairs"] == 0
    assert manifest["complete"] is True
    assert len(bundle.records) == expected_pairs_count

    # Verify all (arm_id, case_id) pairs exist
    recorded_pairs = {(r["arm_id"], r["case_id"]) for r in bundle.records}
    expected_pairs = {(arm, case_id) for arm in DEFAULT_ARMS for case_id in PRIVACY_CASE_IDS}
    assert recorded_pairs == expected_pairs

    # Verify outcome counts sum to planned denominator
    counts = bundle.outcome_counts()
    assert sum(counts.values()) == expected_pairs_count
    assert manifest["denominator_total"] == expected_pairs_count

    # Denominator buckets match manifest
    for bucket in OUTCOME_BUCKETS:
        assert counts[bucket.lower()] == manifest["denominator"][bucket.lower()]

    # Verify digests and required record metadata
    for record in bundle.records:
        assert record["record_kind"] == "pair_result"
        assert record["pair_digest"]
        assert record["seed"] == FIXED_SEED
        assert record["source_commit"] == bundle.source_commit
        assert record["outcome"]["observed_outcome"] in OUTCOME_BUCKETS

    # Honest baseline availability: B0 and B3 are NOT_RUN_EXTERNAL
    b0_records = [r for r in bundle.records if r["arm_id"] == "B0"]
    b3_records = [r for r in bundle.records if r["arm_id"] == "B3"]
    assert all(r["outcome"]["observed_outcome"] == "NOT_RUN_EXTERNAL" for r in b0_records)
    assert all(r["outcome"]["observed_outcome"] == "NOT_RUN_EXTERNAL" for r in b3_records)

    # Implemented arms produce ADMIT / REJECT
    b1_records = [r for r in bundle.records if r["arm_id"] == "B1"]
    b4_records = [r for r in bundle.records if r["arm_id"] == "B4"]
    assert all(r["outcome"]["observed_outcome"] in ("ADMIT", "REJECT") for r in b1_records)
    assert all(r["outcome"]["observed_outcome"] in ("ADMIT", "REJECT") for r in b4_records)


def test_balanced_pairing_across_all_arms() -> None:
    """Every arm evaluates the exact same multiset of cases in identical order."""
    config = CampaignConfig(
        campaign_id="test-balanced-pairing",
        seed=FIXED_SEED,
    )
    bundle = run_campaign(config)

    per_arm_cases: dict[str, list[str]] = {arm: [] for arm in DEFAULT_ARMS}
    for record in bundle.records:
        per_arm_cases[record["arm_id"]].append(record["case_id"])

    expected_cases_list = list(PRIVACY_CASE_IDS)
    for arm_id, cases in per_arm_cases.items():
        assert (
            cases == expected_cases_list
        ), f"Arm {arm_id} did not evaluate identical cases in order"
        assert len(cases) == len(expected_cases_list)


def test_deterministic_re_run_produces_identical_bundle() -> None:
    """Two independent runs with the same fixed seed produce identical records."""
    cfg = CampaignConfig(
        campaign_id="test-determinism",
        seed=FIXED_SEED,
        arm_ids=("B1", "B2", "B4"),
    )
    bundle1 = run_campaign(cfg)
    bundle2 = run_campaign(cfg)

    assert bundle1.manifest["planned_pairs"] == bundle2.manifest["planned_pairs"]
    assert bundle1.manifest["denominator"] == bundle2.manifest["denominator"]
    assert len(bundle1.records) == len(bundle2.records)

    # Compare digests across records
    digests1 = [r["pair_digest"] for r in bundle1.records]
    digests2 = [r["pair_digest"] for r in bundle2.records]
    assert digests1 == digests2

    # Compare observed outcomes
    outcomes1 = [r["outcome"]["observed_outcome"] for r in bundle1.records]
    outcomes2 = [r["outcome"]["observed_outcome"] for r in bundle2.records]
    assert outcomes1 == outcomes2


def test_custom_cases_and_subset_arms() -> None:
    """Custom cases and subset arms execute with exact paired counts."""
    custom_cases = (
        {"case_id": "cust-01", "scenario_class": "fresh_dispatch"},
        {"case_id": "cust-02", "scenario_class": "post_revocation_dispatch"},
    )
    config = CampaignConfig(
        campaign_id="test-custom-cases",
        arm_ids=("B1", "B4"),
        cases=custom_cases,
        seed=FIXED_SEED,
    )
    bundle = run_campaign(config)

    assert len(bundle.records) == 4  # 2 arms x 2 cases
    assert bundle.manifest["complete"] is True
    assert bundle.manifest["planned_pairs"] == 4
    assert bundle.manifest["attempted_pairs"] == 4


def test_resumable_idempotent_journal(tmp_path: Path) -> None:
    """Re-running with a journal executes only uncompleted pairs and performs 0 duplicate runs."""
    journal_file = tmp_path / "test_campaign.journal.jsonl"
    cfg = CampaignConfig(
        campaign_id="test-journal-idempotence",
        arm_ids=("B1", "B2"),
        case_ids=("PC-FRESH-01", "PC-REVOKE-01"),
        seed=FIXED_SEED,
        journal_path=journal_file,
    )

    first_bundle = run_campaign(cfg)
    assert first_bundle.manifest["executed_pairs"] == 4
    assert first_bundle.manifest["resumed_pairs"] == 0
    assert journal_file.is_file()

    # Re-run against the journal: should resume all 4 pairs and execute 0
    second_bundle = run_campaign(cfg)
    assert second_bundle.manifest["executed_pairs"] == 0
    assert second_bundle.manifest["resumed_pairs"] == 4
    assert len(second_bundle.records) == 4

    digests1 = [r["pair_digest"] for r in first_bundle.records]
    digests2 = [r["pair_digest"] for r in second_bundle.records]
    assert digests1 == digests2


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_crashing_arm_recorded_as_execution_error_not_dropped() -> None:
    """An arm that raises an unhandled exception is recorded as EXECUTION_ERROR, not dropped."""

    def crashing_arm(case: dict[str, object], ctx: RunContext) -> Outcome:
        del case, ctx
        raise RuntimeError("simulated arm backend crash")

    custom_cases = (
        {"case_id": "case-crash-1"},
        {"case_id": "case-crash-2"},
    )
    config = CampaignConfig(
        campaign_id="test-crashing-arm",
        arm_ids=("B1", "crasher"),
        cases=custom_cases,
        custom_arms={"crasher": crashing_arm},
        seed=FIXED_SEED,
    )

    # Should not raise; failures are accounted in the denominator
    bundle = run_campaign(config)

    assert bundle.manifest["complete"] is True
    assert bundle.manifest["planned_pairs"] == 4
    assert bundle.manifest["attempted_pairs"] == 4
    assert bundle.manifest["missing_pairs"] == 0

    crasher_records = [r for r in bundle.records if r["arm_id"] == "crasher"]
    assert len(crasher_records) == 2
    for r in crasher_records:
        assert r["outcome"]["observed_outcome"] == "EXECUTION_ERROR"
        assert r["outcome"]["counted_as_success"] is False
        assert "RuntimeError" in r["outcome"]["detail"]

    counts = bundle.outcome_counts()
    assert counts["execution_error"] == 2
    assert bundle.manifest["denominator"]["execution_error"] == 2


def test_unequal_config_seed_drift_refused() -> None:
    """Seed drift between arms is refused before execution starts."""
    # Mapping form with unequal seeds
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                seeds={"B1": 42, "B2": 43},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"

    # Tuple form with unequal seeds
    with pytest.raises(RunnerError) as exc_info2:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                seeds=(42, 43),
            )
        )
    assert exc_info2.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_unequal_config_timeout_refused() -> None:
    """Unequal per-arm timeouts are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                arm_timeouts={"B1": 10.0, "B2": 30.0},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_unequal_config_retry_budget_refused() -> None:
    """Unequal per-arm retry budgets are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                arm_retry_budgets={"B1": 0, "B2": 2},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_unequal_config_backend_refused() -> None:
    """Unequal per-arm execution backends are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                arm_backends={"B1": "in_process", "B2": "cluster"},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_unequal_config_compiler_version_refused() -> None:
    """Unequal per-arm compiler versions are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                arm_compiler_versions={"B1": "gcc-13", "B2": "clang-17"},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_unequal_config_model_version_refused() -> None:
    """Unequal per-arm model versions are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("B1", "B2"),
                arm_model_versions={"B1": "model-v1", "B2": "model-v2"},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_unknown_arm_refused() -> None:
    """An unregistered arm identifier without a custom adapter is refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=("unknown-fictional-arm",),
            )
        )
    assert exc_info.value.reason_code == "UNKNOWN_ARM"


def test_empty_scope_refused() -> None:
    """Empty arm_ids or empty cases list is refused."""
    with pytest.raises(RunnerError) as exc_arm:
        run_campaign(CampaignConfig(arm_ids=()))
    assert exc_arm.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc_cases:
        run_campaign(CampaignConfig(cases=()))
    assert exc_cases.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc_cids:
        run_campaign(CampaignConfig(case_ids=()))
    assert exc_cids.value.reason_code == "EMPTY_SCOPE"


def test_config_malformed_refused() -> None:
    """Invalid configuration type is refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign("not a config object")  # type: ignore[arg-type]
    assert exc_info.value.reason_code == "CONFIG_MALFORMED"


def test_jsonl_bundle_serialization() -> None:
    """RunBundle serializes to valid JSONL matching record_kind conventions."""
    cfg = CampaignConfig(
        campaign_id="test-jsonl",
        arm_ids=("B1",),
        case_ids=("PC-FRESH-01",),
        seed=FIXED_SEED,
    )
    bundle = run_campaign(cfg)
    jsonl_text = bundle.to_jsonl()
    lines = [json.loads(line) for line in jsonl_text.splitlines() if line.strip()]

    assert len(lines) == 2  # 1 pair record + 1 manifest record
    assert lines[0]["record_kind"] == "pair_result"
    assert lines[1]["record_kind"] == "run_manifest"
    assert lines[1]["complete"] is True
