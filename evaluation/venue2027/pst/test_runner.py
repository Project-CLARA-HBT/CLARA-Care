"""Tests for PST-runner (uniform multi-arm execution runner).

Positive controls:
- All planned (arm x case) pairs are accounted for in the RunBundle, with
  mutually exclusive outcome buckets and full denominator coverage.
- Balanced pairing: every arm evaluates the exact same multiset of cases in
  identical order under the same seed, timeout, retry budget, and backend.
- Deterministic re-run: re-running with the same fixed seed produces identical
  pair digests and identical manifest outcome counts.
- Reconstructability and linkability frontier: reconstructability score and
  linkability score are recorded per arm x case pair, proving B0 upper bound,
  B1 reconstructability loss, and B2/B3 recovery with B3 privacy optimization.
- Resumable journal: completed pairs are loaded from the journal; re-run
  performs zero duplicate executions (idempotent).
- Custom case sets and arm subsets execute cleanly.
- JSON and JSONL serialization: RunBundle serializes and deserializes cleanly.

Adversarial controls:
- An arm that crashes (raises an unhandled exception) is recorded as
  EXECUTION_ERROR with the exception class; it is NOT dropped from the
  denominator, and complete=True is preserved.
- An arm that raises TimeoutError is recorded as TIMEOUT, retriable=True,
  and never dropped.
- Unequal arm configurations are refused before execution:
  - Seed drift between arms -> UNEQUAL_ARM_CONFIG
  - Unequal timeouts between arms -> UNEQUAL_ARM_CONFIG
  - Unequal retry budgets between arms -> UNEQUAL_ARM_CONFIG
  - Unequal execution backends between arms -> UNEQUAL_ARM_CONFIG
  - Unequal compiler or model versions between arms -> UNEQUAL_ARM_CONFIG
  - Differing per-arm configurations in arm_configs -> UNEQUAL_ARM_CONFIG
- Unknown arm identifiers without custom adapters -> UNKNOWN_ARM.
- Empty scopes (empty arms or cases) -> EMPTY_SCOPE.
- Duplicate IDs (duplicate arm_ids or case_ids) -> DUPLICATE_ID.
- Invalid timeout or workers -> INVALID_TIMEOUT / INVALID_WORKERS.
- Missing or invalid source commit SHA -> MISSING_SOURCE_SHA.
- Malformed config types -> CONFIG_MALFORMED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import OUTCOME_BUCKETS, Outcome, RunContext
from evaluation.venue2027.pst.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
)
from evaluation.venue2027.pst.runner import (
    DEFAULT_ARMS,
    CampaignConfig,
    RunnerError,
    default_cases,
    run_campaign,
)

FIXED_SEED = 2027
SAMPLE_COMMIT = "75ad321ea230ad398d71f4a0afb26e0cdef83982"


# ===========================================================================
# Positive controls
# ===========================================================================


def test_all_arm_case_pairs_recorded_in_bundle() -> None:
    """Every planned arm x case pair is recorded with mutually exclusive outcomes."""
    config = CampaignConfig(
        campaign_id="test-all-pairs-recorded",
        seed=FIXED_SEED,
        source_commit=SAMPLE_COMMIT,
    )
    bundle = run_campaign(config)

    cases = default_cases()
    expected_pairs_count = len(DEFAULT_ARMS) * len(cases)
    manifest = bundle.manifest

    assert manifest["planned_pairs"] == expected_pairs_count
    assert manifest["attempted_pairs"] == expected_pairs_count
    assert manifest["missing_pairs"] == 0
    assert manifest["complete"] is True
    assert len(bundle.records) == expected_pairs_count

    # Verify all (arm_id, case_id) pairs exist
    recorded_pairs = {(r["arm_id"], r["case_id"]) for r in bundle.records}
    expected_pairs = {(arm, c["case_id"]) for arm in DEFAULT_ARMS for c in cases}
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
        assert record["source_commit"] == SAMPLE_COMMIT
        assert record["outcome"]["observed_outcome"] in OUTCOME_BUCKETS

        # Explicit score fields must exist on every record
        assert "reconstructability_score" in record
        assert "linkability_score" in record


def test_balanced_pairing_identical_conditions() -> None:
    """Every arm evaluates the exact same cases in identical order with identical parameters."""
    config = CampaignConfig(
        campaign_id="test-balanced-pairing",
        seed=FIXED_SEED,
        per_pair_timeout_seconds=30.0,
        retry_budget=0,
        backend="in_process",
    )
    bundle = run_campaign(config)

    expected_cases = [c["case_id"] for c in default_cases()]

    for arm in DEFAULT_ARMS:
        arm_records = [r for r in bundle.records if r["arm_id"] == arm]
        observed_cases = [r["case_id"] for r in arm_records]
        assert observed_cases == expected_cases
        assert all(r["seed"] == FIXED_SEED for r in arm_records)


def test_deterministic_rerun_with_fixed_seed() -> None:
    """Re-running with the same fixed seed produces identical pair digests and counts."""
    config = CampaignConfig(
        campaign_id="test-deterministic-rerun",
        seed=FIXED_SEED,
        source_commit=SAMPLE_COMMIT,
    )

    bundle_1 = run_campaign(config)
    bundle_2 = run_campaign(config)

    assert len(bundle_1.records) == len(bundle_2.records)
    digests_1 = [r["pair_digest"] for r in bundle_1.records]
    digests_2 = [r["pair_digest"] for r in bundle_2.records]
    assert digests_1 == digests_2

    assert bundle_1.outcome_counts() == bundle_2.outcome_counts()


def test_reconstructability_and_linkability_frontier() -> None:
    """Scores are recorded per arm x case pair and demonstrate the frontier."""
    config = CampaignConfig(
        campaign_id="test-frontier-measurement",
        seed=FIXED_SEED,
    )
    bundle = run_campaign(config)

    # Inspect PST-CASE-01-FULL where full evidence exists
    full_records = {r["arm_id"]: r for r in bundle.records if r["case_id"] == "PST-CASE-01-FULL"}

    # B0: 100% reconstructability, high linkability risk
    rec_b0 = full_records[BASELINE_B0]["reconstructability_score"]
    link_b0 = full_records[BASELINE_B0]["linkability_score"]
    assert rec_b0 == 1.0
    assert link_b0 > 0.90

    # B1: stripped receipts -> reconstructability collapses
    rec_b1 = full_records[BASELINE_B1]["reconstructability_score"]
    assert rec_b1 < 0.50

    # B2: cryptographic receipt anchoring recovers reconstructability
    rec_b2 = full_records[BASELINE_B2]["reconstructability_score"]
    link_b2 = full_records[BASELINE_B2]["linkability_score"]
    assert rec_b2 >= 0.85
    assert link_b2 < link_b0

    # B3 (ReceiptMin): recovers reconstructability AND optimizes linkability frontier
    rec_b3 = full_records[BASELINE_B3]["reconstructability_score"]
    link_b3 = full_records[BASELINE_B3]["linkability_score"]
    assert rec_b3 >= 0.85
    assert link_b3 < 0.20
    assert link_b3 < link_b2


def test_resumable_journal_idempotency(tmp_path: Path) -> None:
    """Completed pairs are preserved in journal; re-run performs zero duplicate executions."""
    journal_file = tmp_path / "pst_journal.jsonl"
    config = CampaignConfig(
        campaign_id="test-journal-idempotent",
        seed=FIXED_SEED,
        journal_path=journal_file,
    )

    first_bundle = run_campaign(config)
    assert first_bundle.manifest["resumed_pairs"] == 0
    assert first_bundle.manifest["executed_pairs"] == 16

    # Re-run against the existing journal
    second_bundle = run_campaign(config)
    assert second_bundle.manifest["resumed_pairs"] == 16
    assert second_bundle.manifest["executed_pairs"] == 0
    assert len(second_bundle.records) == 16

    digests_1 = [r["pair_digest"] for r in first_bundle.records]
    digests_2 = [r["pair_digest"] for r in second_bundle.records]
    assert digests_1 == digests_2


def test_custom_cases_and_custom_arms() -> None:
    """Custom cases and custom injected arm adapters execute and record cleanly."""
    custom_case = {
        "case_id": "CUSTOM-CASE-01",
        "family": "full_evidence",
        "events": [
            {
                "event_id": "evt-c01",
                "purpose": "clinical_care",
                "operation": "record_write",
                "policy_epoch": "epoch-1",
                "consent_epoch": "epoch-1",
                "witness_id": "wit-c01",
                "timestamp": "2026-11-15T10:00:00Z",
                "payload": {"med": "amoxicillin"},
            }
        ],
    }

    def custom_adapter(case: Any, ctx: RunContext) -> Outcome:
        del case, ctx
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            detail=json.dumps({"reconstructability": 0.95, "linkability": 0.15}),
        )

    config = CampaignConfig(
        campaign_id="test-custom-scope",
        arm_ids=("custom_arm", BASELINE_B0),
        cases=(custom_case,),
        custom_arms={"custom_arm": custom_adapter},
    )

    bundle = run_campaign(config)
    assert len(bundle.records) == 2
    recorded = {r["arm_id"]: r for r in bundle.records}

    assert recorded["custom_arm"]["outcome"]["observed_outcome"] == "ADMIT"
    assert recorded["custom_arm"]["reconstructability_score"] == 0.95
    assert recorded["custom_arm"]["linkability_score"] == 0.15
    assert recorded[BASELINE_B0]["outcome"]["observed_outcome"] == "ADMIT"


def test_bundle_json_and_jsonl_serialization() -> None:
    """RunBundle serializes to valid dict and JSONL representation."""
    config = CampaignConfig(campaign_id="test-serialization", seed=FIXED_SEED)
    bundle = run_campaign(config)

    bundle_dict = bundle.to_dict()
    assert bundle_dict["campaign_id"] == "test-serialization"
    assert bundle_dict["pair_count"] == 16

    jsonl_str = bundle.to_jsonl()
    lines = [json.loads(line) for line in jsonl_str.splitlines() if line.strip()]
    # 16 pair records + 1 manifest record
    assert len(lines) == 17
    assert lines[-1]["record_kind"] == "run_manifest"
    assert all(entry["record_kind"] == "pair_result" for entry in lines[:-1])


# ===========================================================================
# Adversarial controls
# ===========================================================================


def test_adversarial_crashing_arm_recorded_as_execution_error_not_dropped() -> None:
    """An arm that raises is recorded as EXECUTION_ERROR and NOT dropped from denominator."""

    def exploding_arm(case: Any, ctx: RunContext) -> Outcome:
        del case, ctx
        raise RuntimeError("simulated storage explosion")

    config = CampaignConfig(
        campaign_id="test-crashing-arm",
        arm_ids=("exploding_arm", BASELINE_B0),
        custom_arms={"exploding_arm": exploding_arm},
    )
    bundle = run_campaign(config)

    assert bundle.manifest["planned_pairs"] == 8
    assert bundle.manifest["attempted_pairs"] == 8
    assert bundle.manifest["missing_pairs"] == 0
    assert bundle.manifest["complete"] is True
    assert len(bundle.records) == 8

    crashed = [r for r in bundle.records if r["arm_id"] == "exploding_arm"]
    assert len(crashed) == 4
    for r in crashed:
        assert r["outcome"]["observed_outcome"] == "EXECUTION_ERROR"
        assert r["outcome"]["counted_as_success"] is False
        assert "RuntimeError" in r["outcome"]["detail"]
        assert r["reconstructability_score"] is None
        assert r["linkability_score"] is None

    # Other arm completed successfully
    ok_records = [r for r in bundle.records if r["arm_id"] == BASELINE_B0]
    assert len(ok_records) == 4
    assert all(r["outcome"]["observed_outcome"] in ("ADMIT", "REJECT") for r in ok_records)


def test_adversarial_timeout_recorded_not_dropped() -> None:
    """An arm that raises TimeoutError is recorded as TIMEOUT, retriable=True, not dropped."""

    def timing_out_arm(case: Any, ctx: RunContext) -> Outcome:
        del case, ctx
        raise TimeoutError("per-pair deadline exceeded")

    config = CampaignConfig(
        campaign_id="test-timeout-arm",
        arm_ids=("timing_out_arm",),
        custom_arms={"timing_out_arm": timing_out_arm},
    )
    bundle = run_campaign(config)

    assert bundle.manifest["complete"] is True
    assert len(bundle.records) == 4
    for r in bundle.records:
        assert r["outcome"]["observed_outcome"] == "TIMEOUT"
        assert r["outcome"]["retriable"] is True
        assert r["outcome"]["counted_as_success"] is False


def test_adversarial_unequal_seeds_refused() -> None:
    """Seed drift between arms is refused before execution."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                seeds=(42, 99),
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"

    with pytest.raises(RunnerError) as exc_info2:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_seeds={BASELINE_B0: 42, BASELINE_B1: 99},
            )
        )
    assert exc_info2.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_adversarial_unequal_timeouts_refused() -> None:
    """Mismatched per-arm timeouts are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_timeouts={BASELINE_B0: 30.0, BASELINE_B1: 60.0},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_adversarial_unequal_retry_budgets_refused() -> None:
    """Mismatched per-arm retry budgets are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_retry_budgets={BASELINE_B0: 0, BASELINE_B1: 2},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_adversarial_unequal_backends_refused() -> None:
    """Mismatched execution backends across arms are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_backends={BASELINE_B0: "in_process", BASELINE_B1: "docker"},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_adversarial_unequal_compiler_or_model_versions_refused() -> None:
    """Mismatched compiler or model versions across arms are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_compiler_versions={BASELINE_B0: "3.11.0", BASELINE_B1: "3.12.0"},
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"

    with pytest.raises(RunnerError) as exc_info2:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_model_versions={BASELINE_B0: "v1.0", BASELINE_B1: "v2.0"},
            )
        )
    assert exc_info2.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_adversarial_unequal_arm_configs_refused() -> None:
    """Differing per-arm configuration dictionaries are refused."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(
            CampaignConfig(
                arm_ids=(BASELINE_B0, BASELINE_B1),
                arm_configs={
                    BASELINE_B0: {"mode": "strict"},
                    BASELINE_B1: {"mode": "permissive"},
                },
            )
        )
    assert exc_info.value.reason_code == "UNEQUAL_ARM_CONFIG"


def test_adversarial_unknown_arm_refused() -> None:
    """An unknown arm identifier without a custom adapter fails closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(CampaignConfig(arm_ids=("unregistered_phantom_arm",)))
    assert exc_info.value.reason_code == "UNKNOWN_ARM"


def test_adversarial_empty_scopes_refused() -> None:
    """Empty arm list or empty case list fails closed with EMPTY_SCOPE."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(CampaignConfig(arm_ids=()))
    assert exc_info.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc_info2:
        run_campaign(CampaignConfig(cases=()))
    assert exc_info2.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc_info3:
        run_campaign(CampaignConfig(case_ids=()))
    assert exc_info3.value.reason_code == "EMPTY_SCOPE"


def test_adversarial_duplicate_ids_refused() -> None:
    """Duplicate arm_ids or case_ids fail closed with DUPLICATE_ID."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(CampaignConfig(arm_ids=(BASELINE_B0, BASELINE_B0)))
    assert exc_info.value.reason_code == "DUPLICATE_ID"

    with pytest.raises(RunnerError) as exc_info2:
        run_campaign(CampaignConfig(case_ids=("case-1", "case-1")))
    assert exc_info2.value.reason_code == "DUPLICATE_ID"

    with pytest.raises(RunnerError) as exc_info3:
        run_campaign(
            CampaignConfig(
                cases=(
                    {"case_id": "dup", "events": []},
                    {"case_id": "dup", "events": []},
                )
            )
        )
    assert exc_info3.value.reason_code == "DUPLICATE_ID"


def test_adversarial_invalid_timeout_and_workers_refused() -> None:
    """Negative timeout or workers < 1 fail closed with stable codes."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(CampaignConfig(per_pair_timeout_seconds=-5.0))
    assert exc_info.value.reason_code == "INVALID_TIMEOUT"

    with pytest.raises(RunnerError) as exc_info2:
        run_campaign(CampaignConfig(workers=0))
    assert exc_info2.value.reason_code == "INVALID_WORKERS"


def test_adversarial_missing_source_sha_refused() -> None:
    """An invalid git commit SHA fails closed with MISSING_SOURCE_SHA."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign(CampaignConfig(source_commit="invalid_not_hex"))
    assert exc_info.value.reason_code == "MISSING_SOURCE_SHA"


def test_adversarial_malformed_config_refused() -> None:
    """Non-mapping and non-CampaignConfig objects fail closed."""
    with pytest.raises(RunnerError) as exc_info:
        run_campaign("not_a_config")  # type: ignore[arg-type]
    assert exc_info.value.reason_code == "CONFIG_MALFORMED"
