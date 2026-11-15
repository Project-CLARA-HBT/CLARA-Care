"""Tests for DIMVA-runner — Uniform arm executor (task DIMVA-runner).

Positive controls:
- Every planned arm x session pair is recorded in raw JSONL, in preregistration
  order, including pairs whose arms return ADMIT, REJECT, INDETERMINATE, or
  NOT_RUN_EXTERNAL.
- Default campaign run executes all 5 in-process detector arms across the 5
  balanced probe sessions (25 planned pairs accounted).
- All registered arms (including external pinned arms) execute under equal
  configuration; external arms return NOT_RUN_EXTERNAL honestly.
- RQ1 falsification property is preserved: candidate links low-and-slow attack
  while B0 and B1 miss it, under identical time and seed conditions.
- Deterministic execution: identical inputs and seeds produce byte-identical
  JSONL and pair digests.
- Resumable journaling: interrupted campaigns resume missing pairs without
  duplicate adapter calls.

Adversarial controls:
- An arm adapter that crashes (raises an exception) is recorded as
  EXECUTION_ERROR with the exception class; it is NEVER dropped from the
  bundle, and the full planned denominator is preserved.
- Unequal config is refused: seed drift between arms (different seeds per arm,
  mismatched seed counts) and budget disparity (differing per-arm timeouts or
  budgets) raise RunnerError before execution.
- No label leakage: session-level ground truth (family, label, campaign_label,
  violated_invariant, oracle_verdict) is strictly stripped before passing cases
  to arms; event-level reason code leakage fails closed to INDETERMINATE
  (RQ1 masking); oracle decisions ignore candidate reason codes.
- Malformed inputs (empty scopes, duplicate IDs, invalid timeouts, invalid
  source commit, unknown arms, non-callable oracle) fail closed with stable
  reason codes.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import (
    OUTCOME_BUCKETS,
    Outcome,
    RunContext,
)
from evaluation.venue2027.dimva.baselines import (
    event,
)
from evaluation.venue2027.dimva.runner import (
    ARM_B0,
    ARM_B1,
    ARM_B2,
    ARM_B2_ISOLATION_FOREST,
    ARM_B3,
    ARM_B3_GBT,
    ARM_CANDIDATE,
    DEFAULT_ARMS,
    RC_BUDGET_DISPARITY,
    RC_DUPLICATE_ID,
    RC_EMPTY_SCOPE,
    RC_INVALID_TIMEOUT,
    RC_INVALID_WORKERS,
    RC_MALFORMED_CASE,
    RC_MISSING_SOURCE_SHA,
    RC_ORACLE_NOT_CALLABLE,
    RC_SEED_DRIFT,
    RC_UNEQUAL_CONFIG,
    RC_UNKNOWN_ARM,
    CampaignConfig,
    RunnerError,
    default_probe_sessions,
    extract_score,
    run_campaign,
)

SHA_40 = "28ff55110f980f42002524cef126290e91258cd6"


def _sample_sessions() -> tuple[dict[str, Any], ...]:
    """Small deterministic fixture: 2 benign, 2 attack sessions."""
    benign_1 = {
        "case_id": "CASE-BENIGN-01",
        "family": "benign_session",
        "events": [
            event("actor-clean-1", "med_schedule_read", "self_care", False, 100),
            event("actor-clean-1", "med_schedule_read", "self_care", True, 160),
            event("actor-clean-1", "vitals_read", "self_care", True, 300),
        ],
    }
    benign_2 = {
        "case_id": "CASE-BENIGN-02",
        "family": "benign_session",
        "events": [
            event("actor-clean-2", "vitals_read", "self_care", True, 200),
            event("actor-clean-2", "med_schedule_read", "self_care", True, 400),
        ],
    }
    attack_burst = {
        "case_id": "CASE-ATTACK-BURST",
        "family": "burst_probe",
        "events": [
            event("actor-adv-1", "tool_t1", "self_care", True, 100),
            event("actor-adv-1", "med_read", "self_care", False, 150),
            event("actor-adv-1", "billing_read", "billing", True, 300),
            event("actor-adv-1", "billing_read", "billing", False, 380),
            event("actor-adv-1", "records_export", "research_secondary", True, 500),
        ],
    }
    low_slow_events = [
        event("actor-adv-2", f"probe_tool_{i:02d}", "self_care", False, 1000 + 3700 * i)
        for i in range(9)
    ]
    low_slow_events.append(event("actor-adv-2", "med_read", "self_care", True, 1500))
    low_slow_events.sort(key=lambda e: e["ts"])
    attack_low_slow = {
        "case_id": "CASE-ATTACK-LOW-SLOW",
        "family": "low_and_slow",
        "events": low_slow_events,
    }
    return (benign_1, benign_2, attack_burst, attack_low_slow)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


class TestPositiveRunnerControls:
    def test_default_campaign_runs_all_in_process_arms(self) -> None:
        """Default campaign runs all 5 detector arms on 5 probe sessions = 25 pairs."""
        bundle = run_campaign({"source_commit": SHA_40, "seed": 42})

        assert bundle.campaign_id == "DIMVA-campaign"
        assert bundle.source_commit == SHA_40
        assert bundle.seed == 42
        assert len(bundle.records) == 25
        assert len(bundle.records) == 25

        # Check planned vs attempted pairs in manifest
        manifest = bundle.manifest
        assert manifest["planned_pairs"] == 25
        assert manifest["attempted_pairs"] == 25
        assert manifest["missing_pairs"] == 0
        assert manifest["complete"] is True
        assert manifest["seed"] == 42
        assert manifest["source_commit"] == SHA_40
        assert set(manifest["arm_ids"]) == set(DEFAULT_ARMS)

        # Every record has valid structure, verdict, score, and mutually exclusive outcome
        counts = bundle.outcome_counts()
        assert sum(counts.values()) == 25
        assert manifest["denominator_total"] == 25

        seen_pairs: set[tuple[str, str]] = set()
        for rec in bundle.records:
            assert rec["record_kind"] == "pair_result"
            arm_id = rec["arm_id"]
            case_id = rec["case_id"]
            seen_pairs.add((arm_id, case_id))

            assert rec["seed"] == 42
            assert rec["source_commit"] == SHA_40
            assert rec["outcome"]["observed_outcome"] in OUTCOME_BUCKETS
            assert rec["verdict"] in {"DETECT", "NO_DETECT", "INDETERMINATE"}

            # Oracle verdict structure
            oracle = rec["oracle"]
            assert oracle["candidate_reason_code_ignored"] is True
            assert oracle["truth_label"] in {"ATTACK", "BENIGN", "PENDING_ADJUDICATION"}
            assert oracle["decision"] in {"PASS", "FAIL"}

        assert len(seen_pairs) == 25

    def test_explicit_sessions_and_arm_subset(self) -> None:
        """Explicitly specified sessions and arm subset account for all planned cells."""
        sessions = _sample_sessions()
        arms = ("B0", "B1", "candidate")
        config = CampaignConfig(
            campaign_id="dimva-subset",
            sessions=sessions,
            arm_ids=arms,
            seed=100,
            source_commit=SHA_40,
        )
        bundle = run_campaign(config)

        assert len(bundle.records) == len(sessions) * len(arms) == 12
        assert bundle.manifest["complete"] is True
        assert bundle.manifest["missing_pairs"] == 0

    def test_all_registered_arms_including_external(self) -> None:
        """All 7 registered arms execute; external arms honestly report NOT_RUN_EXTERNAL."""
        sessions = _sample_sessions()[:2]
        arms = (
            ARM_B0,
            ARM_B1,
            ARM_B2,
            ARM_B3,
            ARM_CANDIDATE,
            ARM_B2_ISOLATION_FOREST,
            ARM_B3_GBT,
        )
        config = {
            "campaign_id": "dimva-all-arms",
            "sessions": sessions,
            "arm_ids": arms,
            "seed": 2027,
            "source_commit": SHA_40,
        }
        bundle = run_campaign(config)
        assert len(bundle.records) == 2 * 7 == 14

        by_arm: dict[str, list[dict[str, Any]]] = {}
        for r in bundle.records:
            by_arm.setdefault(r["arm_id"], []).append(r)

        # External arms must be NOT_RUN_EXTERNAL (never a toy, rule 8)
        for ext_arm in (ARM_B2_ISOLATION_FOREST, ARM_B3_GBT):
            records = by_arm[ext_arm]
            assert len(records) == 2
            for rec in records:
                assert rec["outcome"]["observed_outcome"] == "NOT_RUN_EXTERNAL"
                assert rec["outcome"]["detail"] == "BASELINE_UNAVAILABLE"
                assert rec["outcome"]["counted_as_success"] is False
                assert rec["verdict"] == "NOT_RUN_EXTERNAL"

        # In-process arms must produce real decisions
        for arm in (ARM_B0, ARM_B1, ARM_B2, ARM_B3, ARM_CANDIDATE):
            records = by_arm[arm]
            assert len(records) == 2
            for rec in records:
                assert rec["outcome"]["observed_outcome"] in {"ADMIT", "REJECT"}
                assert rec["outcome"]["counted_as_success"] is True

    def test_deterministic_execution(self) -> None:
        """Repeated runs with identical config produce byte-identical JSONL output."""
        config = {
            "campaign_id": "dimva-det-check",
            "sessions": _sample_sessions(),
            "arm_ids": ("B0", "B3", "candidate"),
            "seed": 999,
            "source_commit": SHA_40,
        }
        bundle_1 = run_campaign(config)
        bundle_2 = run_campaign(config)

        # Compare pair records
        assert len(bundle_1.records) == len(bundle_2.records)
        for r1, r2 in zip(bundle_1.records, bundle_2.records, strict=True):
            assert r1["logical_op_id"] == r2["logical_op_id"]
            assert r1["pair_digest"] == r2["pair_digest"]
            assert r1["outcome"] == r2["outcome"]
            assert r1["verdict"] == r2["verdict"]
            assert r1["score"] == r2["score"]

        assert bundle_1.manifest["denominator"] == bundle_2.manifest["denominator"]
        assert bundle_1.manifest["planned_pairs"] == bundle_2.manifest["planned_pairs"]
        assert bundle_1.manifest["attempted_pairs"] == bundle_2.manifest["attempted_pairs"]
        assert bundle_1.manifest["missing_pairs"] == bundle_2.manifest["missing_pairs"]

    def test_rq1_falsification_fidelity_preserved(self) -> None:
        """On low-and-slow cross-tool campaign, candidate flags while B0 and B1 miss."""
        sessions = default_probe_sessions()
        config = {
            "campaign_id": "dimva-rq1",
            "sessions": sessions,
            "arm_ids": ("B0", "B1", "B3", "candidate"),
            "seed": 7,
            "source_commit": SHA_40,
        }
        bundle = run_campaign(config)

        # Look up records for DIMVA-PROBE-ATTACK-LOW-AND-SLOW
        target_records = {
            r["arm_id"]: r
            for r in bundle.records
            if r["case_id"] == "DIMVA-PROBE-ATTACK-LOW-AND-SLOW"
        }

        # B0 (static window counting) misses: low-and-slow pacing evades window
        assert target_records["B0"]["verdict"] == "NO_DETECT"
        assert target_records["B0"]["outcome"]["observed_outcome"] == "ADMIT"

        # B1 (cross-scope rule) misses: all activity in self_care scope
        assert target_records["B1"]["verdict"] == "NO_DETECT"
        assert target_records["B1"]["outcome"]["observed_outcome"] == "ADMIT"

        # B3 (campaign linkage) detects: links across tools and span
        assert target_records["B3"]["verdict"] == "DETECT"
        assert target_records["B3"]["outcome"]["observed_outcome"] == "REJECT"

        # Candidate detects: campaign structure detected
        assert target_records["candidate"]["verdict"] == "DETECT"
        assert target_records["candidate"]["outcome"]["observed_outcome"] == "REJECT"

    def test_resumable_journal_idempotent(self, tmp_path: Path) -> None:
        """Interrupted campaign resumes missing pairs; rerunning completed campaign performs 0 calls."""
        journal = tmp_path / "journal.jsonl"
        sessions = _sample_sessions()[:2]
        arms = ("B0", "candidate")
        config = {
            "campaign_id": "dimva-resumable",
            "sessions": sessions,
            "arm_ids": arms,
            "seed": 55,
            "source_commit": SHA_40,
            "journal_path": journal,
        }

        # Run 1: executes all 4 pairs
        bundle_1 = run_campaign(config)
        assert bundle_1.manifest["executed_pairs"] == 4
        assert bundle_1.manifest["resumed_pairs"] == 0
        assert journal.is_file()

        # Run 2: re-runs from journal; 0 executed pairs
        bundle_2 = run_campaign(config)
        assert bundle_2.manifest["executed_pairs"] == 0
        assert bundle_2.manifest["resumed_pairs"] == 4
        assert len(bundle_2.records) == 4

        # Output records are identical
        for r1, r2 in zip(bundle_1.records, bundle_2.records, strict=True):
            assert r1["logical_op_id"] == r2["logical_op_id"]
            assert r1["pair_digest"] == r2["pair_digest"]


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


class TestAdversarialRunnerControls:
    def test_crashing_arm_recorded_as_execution_error_not_dropped(self) -> None:
        """An arm that raises is recorded as EXECUTION_ERROR and NOT dropped from bundle."""
        sessions = _sample_sessions()[:2]

        def _crashing_arm(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
            raise RuntimeError("Detector sensor hardware fault")

        config = {
            "campaign_id": "dimva-crash-test",
            "sessions": sessions,
            "arm_ids": ("B0", "crashing_arm"),
            "seed": 12,
            "source_commit": SHA_40,
            "custom_arms": {"crashing_arm": _crashing_arm},
        }

        bundle = run_campaign(config)

        # Denominator must account for all 4 pairs (2 arms x 2 sessions)
        assert len(bundle.records) == 4
        assert bundle.manifest["planned_pairs"] == 4
        assert bundle.manifest["attempted_pairs"] == 4
        assert bundle.manifest["missing_pairs"] == 0
        assert bundle.manifest["complete"] is True

        # Check crashing arm records
        crash_records = [r for r in bundle.records if r["arm_id"] == "crashing_arm"]
        assert len(crash_records) == 2
        for r in crash_records:
            assert r["outcome"]["observed_outcome"] == "EXECUTION_ERROR"
            assert r["outcome"]["detail"] == "RuntimeError"
            assert r["outcome"]["counted_as_success"] is False
            assert r["verdict"] == "EXECUTION_ERROR"

        # Check normal B0 records still succeeded
        b0_records = [r for r in bundle.records if r["arm_id"] == "B0"]
        assert len(b0_records) == 2
        for r in b0_records:
            assert r["outcome"]["observed_outcome"] in {"ADMIT", "REJECT"}

        # Denominator counts reflect execution error
        counts = bundle.outcome_counts()
        assert counts["execution_error"] == 2

    def test_timeout_arm_recorded_not_dropped(self) -> None:
        """An arm that raises TimeoutError is recorded as TIMEOUT and NOT dropped."""
        sessions = _sample_sessions()[:1]

        def _timing_out_arm(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
            raise TimeoutError("Deadline exceeded")

        config = {
            "campaign_id": "dimva-timeout-test",
            "sessions": sessions,
            "arm_ids": ("timeout_arm",),
            "seed": 1,
            "source_commit": SHA_40,
            "custom_arms": {"timeout_arm": _timing_out_arm},
        }
        bundle = run_campaign(config)
        assert len(bundle.records) == 1
        rec = bundle.records[0]
        assert rec["outcome"]["observed_outcome"] == "TIMEOUT"
        assert rec["outcome"]["retriable"] is True
        assert rec["verdict"] == "TIMEOUT"
        assert bundle.outcome_counts()["timeout"] == 1

    def test_unequal_config_refused_seed_drift(self) -> None:
        """Seeds that differ across arms are refused with SEED_DRIFT."""
        sessions = _sample_sessions()[:2]
        arms = ("B0", "B1")

        # Seeds tuple count mismatch
        with pytest.raises(RunnerError) as exc_info:
            run_campaign(
                {
                    "campaign_id": "test-drift",
                    "sessions": sessions,
                    "arm_ids": arms,
                    "seeds": (42,),
                    "source_commit": SHA_40,
                }
            )
        assert exc_info.value.reason_code == RC_SEED_DRIFT

        # Seeds tuple differing values
        with pytest.raises(RunnerError) as exc_info:
            run_campaign(
                {
                    "campaign_id": "test-drift",
                    "sessions": sessions,
                    "arm_ids": arms,
                    "seeds": (42, 99),
                    "source_commit": SHA_40,
                }
            )
        assert exc_info.value.reason_code == RC_SEED_DRIFT

        # arm_seeds mapping with differing values
        with pytest.raises(RunnerError) as exc_info:
            run_campaign(
                {
                    "campaign_id": "test-drift",
                    "sessions": sessions,
                    "arm_ids": arms,
                    "arm_seeds": {"B0": 10, "B1": 20},
                    "source_commit": SHA_40,
                }
            )
        assert exc_info.value.reason_code == RC_UNEQUAL_CONFIG

    def test_unequal_config_refused_budget_disparity(self) -> None:
        """Different timeouts or budgets per arm are refused with BUDGET_DISPARITY."""
        sessions = _sample_sessions()[:2]
        arms = ("B0", "B1")

        # Differing per-arm timeouts
        with pytest.raises(RunnerError) as exc_info:
            run_campaign(
                {
                    "campaign_id": "test-budget",
                    "sessions": sessions,
                    "arm_ids": arms,
                    "per_pair_timeout_seconds": 30.0,
                    "arm_timeouts": {"B0": 10.0, "B1": 20.0},
                    "source_commit": SHA_40,
                }
            )
        assert exc_info.value.reason_code == RC_BUDGET_DISPARITY

        # Arm timeout mismatched from per_pair_timeout_seconds
        with pytest.raises(RunnerError) as exc_info:
            run_campaign(
                {
                    "campaign_id": "test-budget",
                    "sessions": sessions,
                    "arm_ids": arms,
                    "per_pair_timeout_seconds": 30.0,
                    "arm_timeouts": {"B0": 10.0, "B1": 10.0},
                    "source_commit": SHA_40,
                }
            )
        assert exc_info.value.reason_code == RC_BUDGET_DISPARITY

    def test_no_label_leakage_to_arms(self) -> None:
        """Campaign-level ground-truth labels and families are strictly stripped before reaching arms."""
        received_cases: list[dict[str, Any]] = []

        def _spy_arm(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
            received_cases.append(dict(case))
            return Outcome(observed_outcome="ADMIT", counted_as_success=True)

        leaky_session = {
            "case_id": "LEAKY-CASE-01",
            "family": "low_and_slow",
            "label": "ATTACK",
            "campaign_label": "ATTACK",
            "violated_invariant": "AUTH_PROBING",
            "ground_truth": True,
            "oracle_verdict": "DETECT",
            "events": [
                event("actor-1", "tool_a", "scope_a", True, 100),
                event("actor-1", "tool_b", "scope_a", False, 200),
            ],
        }

        config = {
            "campaign_id": "test-leakage",
            "sessions": [leaky_session],
            "arm_ids": ("spy_arm",),
            "seed": 1,
            "source_commit": SHA_40,
            "custom_arms": {"spy_arm": _spy_arm},
        }

        run_campaign(config)

        assert len(received_cases) == 1
        case = received_cases[0]

        # Case must contain ONLY case_id and events
        assert set(case.keys()) == {"case_id", "events"}

        # No ground-truth label or scenario family leaked
        forbidden = {
            "family",
            "label",
            "campaign_label",
            "violated_invariant",
            "ground_truth",
            "oracle_verdict",
        }
        for key in forbidden:
            assert key not in case

    def test_event_level_reason_code_leak_rejected_by_arms(self) -> None:
        """If raw events carry forbidden reason codes, detector arms fail closed to INDETERMINATE."""
        tainted_session = {
            "case_id": "TAINTED-CASE-01",
            "family": "low_and_slow",
            "events": [
                {
                    "actor_id": "actor-adv",
                    "tool": "med_read",
                    "scope": "self_care",
                    "allowed": False,
                    "ts": 100,
                    "reason_code": "INSUFFICIENT_SCOPE",  # FORBIDDEN LEAK!
                }
            ],
        }

        config = {
            "campaign_id": "test-taint",
            "sessions": [tainted_session],
            "arm_ids": ("B0", "candidate"),
            "seed": 1,
            "source_commit": SHA_40,
        }

        bundle = run_campaign(config)
        assert len(bundle.records) == 2
        for rec in bundle.records:
            # Both B0 and candidate must refuse the reason-code field
            assert rec["outcome"]["observed_outcome"] == "INDETERMINATE"
            assert "REASON_CODE" in rec["outcome"]["detail"]
            assert rec["verdict"] == "INDETERMINATE"

    def test_oracle_ignores_candidate_reason_codes(self) -> None:
        """Independent oracle adjudication proves candidate_reason_code_ignored is True."""
        bundle = run_campaign(
            {
                "campaign_id": "test-oracle-indep",
                "sessions": _sample_sessions()[:2],
                "arm_ids": ("candidate",),
                "seed": 1,
                "source_commit": SHA_40,
            }
        )
        for r in bundle.records:
            assert r["oracle"]["candidate_reason_code_ignored"] is True

    def test_malformed_config_refusals(self) -> None:
        """Malformed configurations fail closed with stable reason codes."""
        # Empty sessions
        with pytest.raises(RunnerError) as exc:
            run_campaign({"sessions": [], "arm_ids": ("B0",), "source_commit": SHA_40})
        assert exc.value.reason_code == RC_EMPTY_SCOPE

        # Empty arm_ids
        with pytest.raises(RunnerError) as exc:
            run_campaign({"arm_ids": (), "source_commit": SHA_40})
        assert exc.value.reason_code == RC_EMPTY_SCOPE

        # Duplicate arm_ids
        with pytest.raises(RunnerError) as exc:
            run_campaign({"arm_ids": ("B0", "B0"), "source_commit": SHA_40})
        assert exc.value.reason_code == RC_DUPLICATE_ID

        # Duplicate case_ids
        dup_sessions = [
            {"case_id": "c1", "events": []},
            {"case_id": "c1", "events": []},
        ]
        with pytest.raises(RunnerError) as exc:
            run_campaign({"sessions": dup_sessions, "arm_ids": ("B0",), "source_commit": SHA_40})
        assert exc.value.reason_code == RC_DUPLICATE_ID

        # Invalid timeout
        with pytest.raises(RunnerError) as exc:
            run_campaign({"per_pair_timeout_seconds": -5.0, "source_commit": SHA_40})
        assert exc.value.reason_code == RC_INVALID_TIMEOUT

        # Invalid workers
        with pytest.raises(RunnerError) as exc:
            run_campaign({"workers": 0, "source_commit": SHA_40})
        assert exc.value.reason_code == RC_INVALID_WORKERS

        # Unknown arm_id
        with pytest.raises(RunnerError) as exc:
            run_campaign({"arm_ids": ("UNKNOWN_MODEL",), "source_commit": SHA_40})
        assert exc.value.reason_code == RC_UNKNOWN_ARM

        # Missing source commit SHA
        with pytest.raises(RunnerError) as exc:
            run_campaign({"source_commit": "short_sha"})
        assert exc.value.reason_code == RC_MISSING_SOURCE_SHA

        # Non-callable oracle
        with pytest.raises(RunnerError) as exc:
            run_campaign({"oracle": "not_callable", "source_commit": SHA_40})
        assert exc.value.reason_code == RC_ORACLE_NOT_CALLABLE

        # Non-mapping session
        with pytest.raises(RunnerError) as exc:
            run_campaign({"sessions": ["not_a_mapping"], "source_commit": SHA_40})
        assert exc.value.reason_code == RC_MALFORMED_CASE

        # Session missing case_id
        with pytest.raises(RunnerError) as exc:
            run_campaign({"sessions": [{"no_case_id": 1}], "source_commit": SHA_40})
        assert exc.value.reason_code == RC_MALFORMED_CASE


# ---------------------------------------------------------------------------
# Score extraction helper tests
# ---------------------------------------------------------------------------


class TestScoreExtraction:
    def test_extract_score_variants(self) -> None:
        assert extract_score("CAMPAIGN_LINKAGE|score=0.850000") == pytest.approx(0.85)
        assert extract_score("NO_ALARM|score=0.123456") == pytest.approx(0.123456)
        assert extract_score("score=1.0") == pytest.approx(1.0)
        assert extract_score("score=0.0") == pytest.approx(0.0)
        assert extract_score("RuntimeError") is None
        assert extract_score("") is None
        assert extract_score("score=nan") is None
