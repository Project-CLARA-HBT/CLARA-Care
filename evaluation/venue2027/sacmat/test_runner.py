"""Tests for SACMAT-runner (uniform arm executor).

Test suite verifying:
1. Positive controls:
   - Every arm x trace pair is recorded in the run bundle.
   - Deterministic execution: identical configuration produces identical outcomes/records.
   - Idempotent journal resumption: completed pairs are preserved without duplicate execution.
   - All outcomes are mutually exclusive per GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4.
2. Adversarial controls:
   - An arm that crashes/raises is recorded as EXECUTION_ERROR (not silently dropped).
   - An arm that exceeds its deadline is recorded as TIMEOUT.
   - Unequal configurations (seed drift across arms, mismatched per-arm timeouts) are refused.
   - Missing, unknown or duplicate arms fail closed with stable reason codes.
   - Non-mapping or empty configuration fails closed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evaluation.venue2027.sacmat import runner
from evaluation.venue2027.sacmat.runner import (
    ARM_CANDIDATE,
    ARM_CEDAR,
    ARM_COMMON_SAFETY_GATE,
    ARM_NO_DIFFERENTIAL,
    ARM_NO_EXPIRY_CHECK,
    ARM_OPA,
    ARM_OPENFGA,
    ARM_STATIC_ONLY,
    CORE_ENGINE_ARMS,
    CampaignConfig,
    RunnerError,
    run_campaign,
)

SAMPLE_SHA_40 = "28ff55110f980f42002524cef126290e91258cd6"


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "T1_PERMIT",
            "trace": {
                "trace_id": "T1_PERMIT",
                "events": [
                    {
                        "kind": "GRANT",
                        "principal": "patient-a",
                        "tenant": "t1",
                        "resource": "record-1",
                        "purpose": "self_care",
                        "logical_time": 100,
                        "expiry": 9000,
                    },
                    {
                        "kind": "ACCESS",
                        "principal": "patient-a",
                        "tenant": "t1",
                        "resource": "record-1",
                        "purpose": "self_care",
                        "logical_time": 500,
                    },
                ],
            },
            "expected_outcome": "PERMIT",
            "expected_findings": [],
        },
        {
            "case_id": "T2_DENY",
            "trace": {
                "trace_id": "T2_DENY",
                "events": [
                    {
                        "kind": "GRANT",
                        "principal": "patient-b",
                        "tenant": "t1",
                        "resource": "record-1",
                        "purpose": "self_care",
                        "logical_time": 100,
                        "expiry": 500,
                    },
                    {
                        "kind": "ACCESS",
                        "principal": "patient-b",
                        "tenant": "t1",
                        "resource": "record-1",
                        "purpose": "self_care",
                        "logical_time": 1000,
                    },
                ],
            },
            "expected_outcome": "DENY",
            "expected_findings": [],
        },
    ]


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_every_arm_trace_pair_recorded() -> None:
    cases = _sample_cases()
    arm_ids = (ARM_CANDIDATE, ARM_CEDAR, ARM_OPENFGA, ARM_OPA)
    cfg = CampaignConfig(
        campaign_id="test-positive-campaign",
        source_commit=SAMPLE_SHA_40,
        seed=2027,
        arm_ids=arm_ids,
        cases=tuple(cases),
    )
    bundle = run_campaign(cfg)

    # Planned: 4 arms * 2 cases = 8 pairs
    assert bundle.manifest["planned_pairs"] == 8
    assert bundle.manifest["attempted_pairs"] == 8
    assert bundle.manifest["missing_pairs"] == 0
    assert len(bundle.records) == 8

    recorded_pairs = {(r["arm_id"], r["case_id"]) for r in bundle.records}
    expected_pairs = {(a, c["case_id"]) for a in arm_ids for c in cases}
    assert recorded_pairs == expected_pairs

    counts = bundle.outcome_counts()
    assert sum(counts.values()) == 8
    # All observed outcomes are valid buckets
    for r in bundle.records:
        assert r["outcome"]["observed_outcome"].lower() in counts
        assert "pair_digest" in r
        assert r["source_commit"] == SAMPLE_SHA_40


def test_positive_deterministic_execution() -> None:
    cases = _sample_cases()
    cfg = CampaignConfig(
        campaign_id="test-determinism",
        source_commit=SAMPLE_SHA_40,
        seed=2027,
        arm_ids=(ARM_CANDIDATE, ARM_CEDAR),
        cases=tuple(cases),
    )
    bundle1 = run_campaign(cfg)
    bundle2 = run_campaign(cfg)

    # Digests of each pair result are deterministic
    assert [r["pair_digest"] for r in bundle1.records] == [
        r["pair_digest"] for r in bundle2.records
    ]
    # Denominators and outcome counts match identically
    assert bundle1.outcome_counts() == bundle2.outcome_counts()
    assert bundle1.manifest["planned_pairs"] == bundle2.manifest["planned_pairs"]
    assert bundle1.manifest["attempted_pairs"] == bundle2.manifest["attempted_pairs"]


def test_positive_default_corpus_execution() -> None:
    # Runs the full default generated temporal corpus (9 traces * 4 arms = 36 pairs)
    cfg = {
        "campaign_id": "test-default-corpus",
        "source_commit": SAMPLE_SHA_40,
        "seed": 2027,
        "arm_ids": CORE_ENGINE_ARMS,
    }
    bundle = run_campaign(cfg)
    assert bundle.manifest["planned_pairs"] == 36
    assert bundle.manifest["attempted_pairs"] == 36
    assert bundle.manifest["missing_pairs"] == 0


def test_positive_ablation_arms_supported() -> None:
    cases = _sample_cases()
    cfg = {
        "campaign_id": "test-ablations",
        "source_commit": SAMPLE_SHA_40,
        "seed": 2027,
        "arm_ids": [
            ARM_STATIC_ONLY,
            ARM_NO_DIFFERENTIAL,
            ARM_NO_EXPIRY_CHECK,
            ARM_COMMON_SAFETY_GATE,
        ],
        "cases": cases,
    }
    bundle = run_campaign(cfg)
    assert bundle.manifest["planned_pairs"] == 8
    assert bundle.manifest["attempted_pairs"] == 8


def test_positive_journal_resumption(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    cases = _sample_cases()
    cfg = CampaignConfig(
        campaign_id="test-resumption",
        source_commit=SAMPLE_SHA_40,
        seed=2027,
        arm_ids=(ARM_CANDIDATE, ARM_CEDAR),
        cases=tuple(cases),
        journal_path=journal,
    )
    bundle1 = run_campaign(cfg)
    assert bundle1.manifest["attempted_pairs"] == 4
    assert bundle1.manifest["resumed_pairs"] == 0
    assert bundle1.manifest["executed_pairs"] == 4

    # Second run should resume all 4 from journal
    bundle2 = run_campaign(cfg)
    assert bundle2.manifest["attempted_pairs"] == 4
    assert bundle2.manifest["resumed_pairs"] == 4
    assert bundle2.manifest["executed_pairs"] == 0
    assert [r["pair_digest"] for r in bundle1.records] == [
        r["pair_digest"] for r in bundle2.records
    ]


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_arm_crash_recorded_not_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = _sample_cases()[:1]  # 1 case

    def faulty_candidate(case: Any, ctx: Any = None) -> Any:
        raise RuntimeError("Simulated PDP runtime crash")

    monkeypatch.setattr(runner.candidate, "run_candidate", faulty_candidate)

    cfg = CampaignConfig(
        campaign_id="test-crash",
        source_commit=SAMPLE_SHA_40,
        seed=2027,
        arm_ids=(ARM_CANDIDATE, ARM_CEDAR),
        cases=tuple(cases),
    )
    bundle = run_campaign(cfg)
    assert bundle.manifest["planned_pairs"] == 2
    assert bundle.manifest["attempted_pairs"] == 2
    assert bundle.manifest["missing_pairs"] == 0

    records_by_arm = {r["arm_id"]: r for r in bundle.records}
    crashed = records_by_arm[ARM_CANDIDATE]
    assert crashed["outcome"]["observed_outcome"] == "EXECUTION_ERROR"
    assert "RuntimeError" in crashed["outcome"]["detail"]
    assert crashed["outcome"]["counted_as_success"] is False

    # The other arm should still have executed normally
    cedar_rec = records_by_arm[ARM_CEDAR]
    assert cedar_rec["outcome"]["observed_outcome"] in ("ADMIT", "REJECT")


def test_adversarial_arm_timeout_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = _sample_cases()[:1]

    def slow_candidate(case: Any, ctx: Any = None) -> Any:
        raise TimeoutError("Simulated arm timeout")

    monkeypatch.setattr(runner.candidate, "run_candidate", slow_candidate)

    cfg = CampaignConfig(
        campaign_id="test-timeout",
        source_commit=SAMPLE_SHA_40,
        seed=2027,
        arm_ids=(ARM_CANDIDATE,),
        cases=tuple(cases),
    )
    bundle = run_campaign(cfg)
    rec = bundle.records[0]
    assert rec["outcome"]["observed_outcome"] == "TIMEOUT"
    assert rec["outcome"]["counted_as_success"] is False


def test_adversarial_seed_drift_refused() -> None:
    cfg = {
        "campaign_id": "test-drift",
        "source_commit": SAMPLE_SHA_40,
        "seeds": [2027, 2028],  # Unequal seeds across arms!
        "arm_ids": [ARM_CANDIDATE, ARM_CEDAR],
    }
    with pytest.raises(RunnerError) as exc:
        run_campaign(cfg)
    assert exc.value.reason_code == "UNEQUAL_CONFIG_REFUSED"


def test_adversarial_mismatched_timeouts_refused() -> None:
    cfg = {
        "campaign_id": "test-unequal-timeout",
        "source_commit": SAMPLE_SHA_40,
        "seed": 2027,
        "arm_ids": [ARM_CANDIDATE, ARM_CEDAR],
        "per_arm_timeouts": {ARM_CANDIDATE: 10.0, ARM_CEDAR: 20.0},
    }
    with pytest.raises(RunnerError) as exc:
        run_campaign(cfg)
    assert exc.value.reason_code == "UNEQUAL_CONFIG_REFUSED"


def test_adversarial_unknown_arm_refused() -> None:
    cfg = {
        "campaign_id": "test-unknown-arm",
        "source_commit": SAMPLE_SHA_40,
        "seed": 2027,
        "arm_ids": ["non_existent_engine"],
    }
    with pytest.raises(RunnerError) as exc:
        run_campaign(cfg)
    assert exc.value.reason_code == "UNKNOWN_ARM"


def test_adversarial_empty_arms_refused() -> None:
    cfg = {
        "campaign_id": "test-empty-arms",
        "source_commit": SAMPLE_SHA_40,
        "seed": 2027,
        "arm_ids": [],
    }
    with pytest.raises(RunnerError) as exc:
        run_campaign(cfg)
    assert exc.value.reason_code == "EMPTY_ARMS"


def test_adversarial_config_not_mapping() -> None:
    with pytest.raises(RunnerError) as exc:
        run_campaign(["not", "a", "dict"])
    assert exc.value.reason_code == "CONFIG_NOT_A_MAPPING"


def test_adversarial_invalid_source_commit() -> None:
    cfg = {
        "campaign_id": "test-invalid-sha",
        "source_commit": "short_sha",
        "seed": 2027,
        "arm_ids": [ARM_CANDIDATE],
    }
    with pytest.raises(RunnerError) as exc:
        run_campaign(cfg)
    assert exc.value.reason_code == "MISSING_SOURCE_SHA"
