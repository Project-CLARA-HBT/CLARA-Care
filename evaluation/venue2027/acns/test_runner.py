"""Tests for ACNS-runner — Uniform arm executor (SoK reference classes).

Positive controls:
- Every reference-class x record pair is recorded in preregistration order.
- Deterministic same-config executions produce identical pair digests.
- Provenance metadata (source_commit, seed, python_version, harness_version) is complete.
- Evidence-boundary verdicts from baselines and independent oracle are recorded.
- Mutually exclusive outcomes partition the planned denominator.
- Resumption and idempotence over journal files.
- Parallel worker slicing accounts for every cell.
- Custom subsets and candidate instrument arm support.

Adversarial controls:
- A reference class that crashes is recorded as EXECUTION_ERROR, not dropped; denominator stays complete.
- Unequal config is strictly refused (unequal seeds, arm_configs, timeouts, retry budgets).
- Empty scope (no arms or cases) and duplicate IDs are refused fail-closed.
- Unknown arm without injected adapter is refused (no constant-allow stub).
- Invalid source commit SHA is refused.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import HARNESS_VERSION, Outcome, RunContext
from evaluation.venue2027.acns.runner import (
    DEFAULT_ARM_IDS,
    DEFAULT_CASE_IDS,
    CampaignConfig,
    RunnerError,
    run_campaign,
)

SHA_40 = "28ff55110f980f42002524cef126290e91258cd6"


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_default_campaign_records_every_pair() -> None:
    """Default campaign executes 4 reference classes x 4 evidence records = 16 pairs."""
    bundle = run_campaign(CampaignConfig(source_commit=SHA_40))
    assert bundle.harness_version == HARNESS_VERSION
    assert bundle.manifest["complete"] is True
    assert bundle.manifest["planned_pairs"] == 16
    assert bundle.manifest["attempted_pairs"] == 16
    assert bundle.manifest["missing_pairs"] == 0
    assert len(bundle.records) == 16

    expected_pairs = [(arm, case) for arm in DEFAULT_ARM_IDS for case in DEFAULT_CASE_IDS]
    actual_pairs = [(r["arm_id"], r["case_id"]) for r in bundle.records]
    assert actual_pairs == expected_pairs


def test_positive_deterministic_runs_produce_identical_digests() -> None:
    """Same campaign configuration produces byte-identical pair digests."""
    cfg = CampaignConfig(source_commit=SHA_40, seed=123)
    b1 = run_campaign(cfg)
    b2 = run_campaign(cfg)
    assert [r["pair_digest"] for r in b1.records] == [r["pair_digest"] for r in b2.records]
    assert b1.manifest["planned_pairs"] == b2.manifest["planned_pairs"]
    assert b1.manifest["denominator"] == b2.manifest["denominator"]


def test_positive_provenance_metadata_recorded() -> None:
    """Every pair record and manifest carries full provenance metadata."""
    bundle = run_campaign(CampaignConfig(source_commit=SHA_40, seed=99))
    assert bundle.source_commit == SHA_40
    assert bundle.seed == 99
    assert bundle.manifest["seed"] == 99
    assert bundle.manifest["wall_seconds"] >= 0

    for r in bundle.records:
        assert r["source_commit"] == SHA_40
        assert r["seed"] == 99
        assert r["harness_version"] == HARNESS_VERSION
        assert r["python_version"]
        assert r["duration_seconds"] >= 0
        assert len(r["pair_digest"]) == 64
        assert r["logical_op_id"] == f"{bundle.campaign_id}:{r['arm_id']}::{r['case_id']}"


def test_positive_evidence_boundary_verdicts_and_oracle_adjudication() -> None:
    """Records contain structured evidence-boundary verdicts and oracle decisions."""
    bundle = run_campaign(CampaignConfig(source_commit=SHA_40))
    by_arm_case = {(r["arm_id"], r["case_id"]): r for r in bundle.records}

    # B3-evidence-boundary-aware matches independent oracle exactly across all 4 records
    b3_bound = by_arm_case[("B3-evidence-boundary-aware", "sok-claim-record-1/bound")]
    assert b3_bound["outcome"]["observed_outcome"] == "ADMIT"
    assert b3_bound["oracle"]["expected_outcome"] == "ADMIT"
    assert b3_bound["oracle"]["decision"] == "PASS"

    b3_downgraded = by_arm_case[("B3-evidence-boundary-aware", "sok-claim-record-2/downgraded")]
    assert b3_downgraded["outcome"]["observed_outcome"] == "REJECT"
    assert b3_downgraded["oracle"]["expected_outcome"] == "REJECT"
    assert b3_downgraded["oracle"]["decision"] == "PASS"

    b3_unbound = by_arm_case[("B3-evidence-boundary-aware", "sok-claim-record-3/unbound")]
    assert b3_unbound["outcome"]["observed_outcome"] == "REJECT"
    assert b3_unbound["oracle"]["expected_outcome"] == "REJECT"
    assert b3_unbound["oracle"]["decision"] == "PASS"

    b3_replayed = by_arm_case[("B3-evidence-boundary-aware", "sok-claim-record-4/replayed")]
    assert b3_replayed["outcome"]["observed_outcome"] == "REJECT"
    assert b3_replayed["oracle"]["expected_outcome"] == "REJECT"
    assert b3_replayed["oracle"]["decision"] == "PASS"

    # Weaker stances show their defining blind spots (oracle decision FAIL on unpoliced gaps)
    b0_downgraded = by_arm_case[("B0-attestation-only", "sok-claim-record-2/downgraded")]
    assert b0_downgraded["outcome"]["observed_outcome"] == "ADMIT"
    assert b0_downgraded["oracle"]["decision"] == "FAIL"

    b1_replayed = by_arm_case[("B1-receipt-without-binding", "sok-claim-record-4/replayed")]
    assert b1_replayed["outcome"]["observed_outcome"] == "ADMIT"
    assert b1_replayed["oracle"]["decision"] == "FAIL"

    b2_unbound = by_arm_case[("B2-timestamp-only", "sok-claim-record-3/unbound")]
    assert b2_unbound["outcome"]["observed_outcome"] == "ADMIT"
    assert b2_unbound["oracle"]["decision"] == "FAIL"


def test_positive_mutually_exclusive_outcomes_partition_denominator() -> None:
    """Outcome counts sum to denominator_total with no double-counting."""
    bundle = run_campaign(CampaignConfig(source_commit=SHA_40))
    counts = bundle.outcome_counts()
    assert sum(counts.values()) == 16
    assert bundle.manifest["denominator_total"] == 16
    assert bundle.manifest["denominator"]["admit"] == counts["admit"]
    assert bundle.manifest["denominator"]["reject"] == counts["reject"]


def test_positive_custom_subset_cases_and_arms() -> None:
    """Run campaign over a specified subset of arms and cases."""
    cfg = CampaignConfig(
        arm_ids=("B0-attestation-only", "B3-evidence-boundary-aware"),
        case_ids=("sok-claim-record-1/bound", "sok-claim-record-2/downgraded"),
        source_commit=SHA_40,
    )
    bundle = run_campaign(cfg)
    assert len(bundle.records) == 4
    assert bundle.manifest["planned_pairs"] == 4
    assert bundle.manifest["attempted_pairs"] == 4


def test_positive_candidate_arm_supported() -> None:
    """The candidate SoK instrument arm can be run alongside reference classes."""
    cfg = CampaignConfig(
        arm_ids=("B3-evidence-boundary-aware", "candidate"),
        case_ids=("sok-claim-record-1/bound",),
        source_commit=SHA_40,
    )
    bundle = run_campaign(cfg)
    assert len(bundle.records) == 2
    assert {r["arm_id"] for r in bundle.records} == {"B3-evidence-boundary-aware", "candidate"}


def test_positive_resumption_and_idempotence(tmp_path: Path) -> None:
    """Resuming a journal completes only missing pairs and is idempotent."""
    journal = tmp_path / "journal.jsonl"
    cfg = CampaignConfig(
        arm_ids=("B0-attestation-only", "B3-evidence-boundary-aware"),
        case_ids=("sok-claim-record-1/bound", "sok-claim-record-2/downgraded"),
        source_commit=SHA_40,
        journal_path=journal,
    )
    bundle1 = run_campaign(cfg)
    assert bundle1.manifest["executed_pairs"] == 4
    assert bundle1.manifest["resumed_pairs"] == 0

    # Second run against completed journal performs zero adapter calls
    bundle2 = run_campaign(cfg)
    assert bundle2.manifest["executed_pairs"] == 0
    assert bundle2.manifest["resumed_pairs"] == 4
    assert [r["pair_digest"] for r in bundle1.records] == [
        r["pair_digest"] for r in bundle2.records
    ]


def test_positive_parallel_workers() -> None:
    """Worker concurrency partitions work and preserves all pairs."""
    bundle = run_campaign(CampaignConfig(source_commit=SHA_40, workers=2))
    assert len(bundle.records) == 16
    assert bundle.manifest["complete"] is True


def test_positive_to_jsonl_and_output_path(tmp_path: Path) -> None:
    """Campaign output can be written to disk and parsed back as JSONL."""
    out_file = tmp_path / "bundle.jsonl"
    run_campaign(CampaignConfig(source_commit=SHA_40, output_path=out_file))
    assert out_file.is_file()
    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 17  # 16 pair_results + 1 run_manifest
    assert lines[-1]["record_kind"] == "run_manifest"
    assert all(line["record_kind"] == "pair_result" for line in lines[:-1])


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_class_crash_recorded_as_execution_error_not_dropped() -> None:
    """A crashing reference class is recorded as EXECUTION_ERROR, not dropped."""
    calls: list[str] = []

    def crashing_arm(case: Any, ctx: RunContext) -> Outcome:
        calls.append(case["case_id"])
        if "downgraded" in case["case_id"]:
            raise RuntimeError("simulated adapter exception")
        return Outcome(observed_outcome="ADMIT", counted_as_success=True)

    cfg = CampaignConfig(
        arm_ids=("B0-attestation-only", "crashing-arm"),
        case_ids=("sok-claim-record-1/bound", "sok-claim-record-2/downgraded"),
        source_commit=SHA_40,
        arms={"crashing-arm": crashing_arm},
    )
    bundle = run_campaign(cfg)

    # 4 pairs planned, 4 pairs attempted; nothing dropped
    assert bundle.manifest["planned_pairs"] == 4
    assert bundle.manifest["attempted_pairs"] == 4
    assert bundle.manifest["missing_pairs"] == 0
    assert bundle.manifest["complete"] is True

    errors = [r for r in bundle.records if r["outcome"]["observed_outcome"] == "EXECUTION_ERROR"]
    assert len(errors) == 1
    assert errors[0]["arm_id"] == "crashing-arm"
    assert errors[0]["case_id"] == "sok-claim-record-2/downgraded"
    assert errors[0]["outcome"]["detail"] == "RuntimeError"
    assert errors[0]["outcome"]["counted_as_success"] is False

    counts = bundle.outcome_counts()
    assert counts["execution_error"] == 1
    assert counts["admit"] == 3


def test_adversarial_unequal_seeds_refused() -> None:
    """Passing different seeds across arms is refused with UNEQUAL_CONFIG."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(
            {
                "arm_ids": ("B0-attestation-only", "B1-receipt-without-binding"),
                "seeds": (42, 43),
                "source_commit": SHA_40,
            }
        )
    assert exc.value.reason_code == "UNEQUAL_CONFIG"


def test_adversarial_unequal_arm_configs_refused() -> None:
    """Differing arm configurations across comparison arms are strictly refused."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(
            {
                "arm_ids": ("B0-attestation-only", "B1-receipt-without-binding"),
                "arm_configs": {
                    "B0-attestation-only": {"budget": 10},
                    "B1-receipt-without-binding": {"budget": 20},
                },
                "source_commit": SHA_40,
            }
        )
    assert exc.value.reason_code == "UNEQUAL_CONFIG"


def test_adversarial_unequal_timeouts_refused() -> None:
    """Unequal per-arm timeouts are refused."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(
            {
                "arm_ids": ("B0-attestation-only", "B1-receipt-without-binding"),
                "arm_timeouts": {
                    "B0-attestation-only": 10.0,
                    "B1-receipt-without-binding": 20.0,
                },
                "source_commit": SHA_40,
            }
        )
    assert exc.value.reason_code == "UNEQUAL_CONFIG"


def test_adversarial_unequal_retry_budgets_refused() -> None:
    """Unequal per-arm retry budgets are refused."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(
            {
                "arm_ids": ("B0-attestation-only", "B1-receipt-without-binding"),
                "arm_retry_budgets": {
                    "B0-attestation-only": 0,
                    "B1-receipt-without-binding": 3,
                },
                "source_commit": SHA_40,
            }
        )
    assert exc.value.reason_code == "UNEQUAL_CONFIG"


def test_adversarial_empty_scope_refused() -> None:
    """Empty arm list or case list is refused fail-closed."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(CampaignConfig(arm_ids=(), source_commit=SHA_40))
    assert exc.value.reason_code == "EMPTY_SCOPE"

    with pytest.raises(RunnerError) as exc:
        run_campaign(CampaignConfig(case_ids=(), source_commit=SHA_40))
    assert exc.value.reason_code == "EMPTY_SCOPE"


def test_adversarial_duplicate_ids_refused() -> None:
    """Duplicate arm_ids or case_ids are refused."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(
            CampaignConfig(
                arm_ids=("B0-attestation-only", "B0-attestation-only"),
                source_commit=SHA_40,
            )
        )
    assert exc.value.reason_code == "DUPLICATE_ID"

    with pytest.raises(RunnerError) as exc:
        run_campaign(
            CampaignConfig(
                case_ids=("sok-claim-record-1/bound", "sok-claim-record-1/bound"),
                source_commit=SHA_40,
            )
        )
    assert exc.value.reason_code == "DUPLICATE_ID"


def test_adversarial_unknown_arm_refused() -> None:
    """Unregistered arm without injected adapter is refused."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(CampaignConfig(arm_ids=("B99-fake-stub",), source_commit=SHA_40))
    assert exc.value.reason_code == "UNKNOWN_ARM"


def test_adversarial_invalid_source_commit_refused() -> None:
    """Non-40-hex source commit is refused."""
    with pytest.raises(RunnerError) as exc:
        run_campaign(CampaignConfig(source_commit="not-a-sha"))
    assert exc.value.reason_code == "INVALID_SOURCE_SHA"
