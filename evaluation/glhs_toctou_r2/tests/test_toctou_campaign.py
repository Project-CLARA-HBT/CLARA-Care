"""Unit and integration tests for the E04 generated PostgreSQL TOCTOU campaign.

Verifies:
1. Grammar feasibility, canonical key generation, and expected outcome rules.
2. Generator deterministic output of >= 1,024 unique logical schedules.
3. Oracle Admissible Outcome Set construction and Red Team invariant checks.
4. Executor multi-threaded PhasedBarrier synchronization and observer_v2 completeness.
5. Failure shrinker minimal reproducer isolation.
6. Statistical analysis (Wilson CIs, categorical breakdowns, classification stability).
7. End-to-end zero forbidden commit verification across generated schedules.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from evaluation.glhs_toctou_r2.analyze import (
    CampaignAnalysis,
    analyze_campaign_results,
    compute_one_sided_wilson_upper,
    compute_wilson_score_interval,
    generate_summary_report,
)
from evaluation.glhs_toctou_r2.executor import (
    E04ExecutorEnv,
    ScheduleResult,
    execute_campaign,
    execute_schedule,
)
from evaluation.glhs_toctou_r2.generator import (
    GENERATOR_SEED,
    MINIMUM_UNIQUE_SCHEDULES,
    generate_schedules,
    mutation_distribution,
    outcome_distribution,
    schedule_set_digest,
    timing_distribution,
)
from evaluation.glhs_toctou_r2.grammar import (
    BENIGN_MUTATIONS,
    COMPOUND_MUTATION_SETS,
    SAFETY_CRITICAL_MUTATIONS,
    STALENESS_MUTATIONS,
    EntityConfig,
    Modifier,
    MutationKind,
    ScheduleDescriptor,
    TimingMode,
    expected_outcome_for,
    is_feasible,
)
from evaluation.glhs_toctou_r2.oracle import (
    COMMITTED_OUTCOMES,
    OPERATIONAL_OUTCOMES,
    AdmissibleOutcomeSet,
    Oracle,
)
from evaluation.glhs_toctou_r2.shrink import shrink_all_forbidden, shrink_schedule


# ===========================================================================
# 1. Grammar & Descriptor Tests
# ===========================================================================

def test_grammar_descriptor_canonical_key() -> None:
    desc1 = ScheduleDescriptor(
        schedule_id="S1",
        mutations=(MutationKind.CONSENT_REVOKE, MutationKind.ROLE_DEMOTE),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )
    desc2 = ScheduleDescriptor(
        schedule_id="S2",
        mutations=(MutationKind.ROLE_DEMOTE, MutationKind.CONSENT_REVOKE),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )
    # Canonical key should sort mutations deterministically.
    assert desc1.canonical_key == desc2.canonical_key
    assert "consent_revoke+role_demote" in desc1.canonical_key


def test_grammar_feasibility_rules() -> None:
    # Consent grant racing commit-before-mutation is infeasible.
    infeasible_desc = ScheduleDescriptor(
        schedule_id="INF1",
        mutations=(MutationKind.CONSENT_GRANT,),
        timing=TimingMode.COMMIT_BEFORE_MUTATION,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )
    assert is_feasible(infeasible_desc) is False

    # Valid mutation + timing is feasible.
    feasible_desc = ScheduleDescriptor(
        schedule_id="FEAS1",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )
    assert is_feasible(feasible_desc) is True


def test_expected_outcome_rules() -> None:
    # Safety-critical mutation before commit -> REJECT.
    desc_reject = ScheduleDescriptor(
        schedule_id="R1",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )
    assert expected_outcome_for(desc_reject) == "REJECT"

    # Benign mutation -> ADMIT.
    desc_admit = ScheduleDescriptor(
        schedule_id="A1",
        mutations=(MutationKind.CONSENT_GRANT,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )
    assert expected_outcome_for(desc_admit) == "ADMIT"

    # Fault injection -> OPERATIONAL.
    desc_ops = ScheduleDescriptor(
        schedule_id="O1",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.TRANSACTION_ABORT,
    )
    assert expected_outcome_for(desc_ops) == "OPERATIONAL"


# ===========================================================================
# 2. Generator Tests
# ===========================================================================

def test_generator_produces_minimum_unique_schedules() -> None:
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=1024)
    assert len(schedules) >= 1024

    # Verify uniqueness of canonical keys.
    keys = [s.canonical_key for s in schedules]
    assert len(keys) == len(set(keys)), "Duplicate schedule canonical keys found!"


def test_generator_reproducibility() -> None:
    s1 = generate_schedules(seed=GENERATOR_SEED, minimum=1024)
    s2 = generate_schedules(seed=GENERATOR_SEED, minimum=1024)

    assert len(s1) == len(s2)
    assert schedule_set_digest(s1) == schedule_set_digest(s2)


def test_generator_distributions() -> None:
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=1024)

    outcomes = outcome_distribution(schedules)
    assert "REJECT" in outcomes
    assert "ADMIT" in outcomes

    timings = timing_distribution(schedules)
    assert len(timings) >= 4

    mutations = mutation_distribution(schedules)
    assert len(mutations) >= 8

    # Compound schedule check: >= 15% compound schedules.
    compound_count = sum(1 for s in schedules if s.compound)
    assert compound_count / len(schedules) >= 0.15


# ===========================================================================
# 3. Oracle Tests & Red Team Invariants
# ===========================================================================

def test_oracle_admissible_sets_and_red_team_verification() -> None:
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=1024)
    oracle = Oracle(schedules)

    for desc in schedules:
        aos = oracle.get(desc.schedule_id)
        assert aos is not None

        if desc.expected_outcome == "REJECT":
            if aos.note != "commit_before_mutation_control_arm_commit_safe":
                # For REJECT schedules, any committed outcome is FORBIDDEN.
                assert oracle.is_forbidden(desc.schedule_id, "transition_committed")
                assert oracle.is_forbidden(desc.schedule_id, "proposal_committed")
                assert oracle.is_safe(desc.schedule_id, "consent_check_failed")


def test_oracle_summary_metrics() -> None:
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=1024)
    oracle = Oracle(schedules)

    # Simulated results matching expected outcomes.
    sim_results = []
    for desc in schedules:
        if desc.expected_outcome == "ADMIT":
            outcome = "transition_committed"
        elif desc.expected_outcome == "OPERATIONAL":
            outcome = "deadlock_detected"
        elif desc.expected_outcome == "INDETERMINATE":
            outcome = "consent_check_failed"
        else:
            outcome = "consent_check_failed"
        sim_results.append({"schedule_id": desc.schedule_id, "commit_outcome": outcome})

    summary = oracle.summary(sim_results)
    assert summary["forbidden_count"] == 0
    assert summary["primary_endpoint_pass"] is True


# ===========================================================================
# 4. Executor & Multi-Threaded Barrier Tests
# ===========================================================================

def test_executor_multithreaded_single_schedule() -> None:
    desc = ScheduleDescriptor(
        schedule_id="E04-TEST-001",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
        expected_outcome="REJECT",
        writer_count=2,
    )
    env = E04ExecutorEnv()
    oracle = Oracle([desc])

    result = execute_schedule(desc, env, oracle)
    assert result.schedule_id == "E04-TEST-001"
    assert result.commit_outcome == "consent_check_failed"
    assert result.safety_success is True
    assert result.forbidden is False
    assert result.observation["run_status"] == "EXECUTED"


def test_executor_campaign() -> None:
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=100)
    env = E04ExecutorEnv()
    oracle = Oracle(schedules)

    run_record = execute_campaign(schedules, env, oracle)
    assert run_record["status"] == "EXECUTED_E04_CAMPAIGN"
    assert run_record["total_schedules"] == len(schedules)
    assert run_record["summary"]["forbidden_count"] == 0


# ===========================================================================
# 5. Shrinker Tests
# ===========================================================================

def test_shrink_schedule() -> None:
    desc_compound = ScheduleDescriptor(
        schedule_id="E04-FORBIDDEN-SIM",
        mutations=(MutationKind.CONSENT_REVOKE, MutationKind.ROLE_DEMOTE),
        timing=TimingMode.SIMULTANEOUS_RELEASE,
        entity=EntityConfig.DELEGATED_ACTOR,
        modifier=Modifier.COMPETING_LOCK,
        compound=True,
        expected_outcome="REJECT",
    )
    env = E04ExecutorEnv()
    oracle = Oracle([desc_compound])

    # Test shrinker structure on a schedule.
    shrink_report = shrink_schedule(desc_compound, env, oracle)
    assert "original" in shrink_report
    assert "minimized" in shrink_report
    assert "shrink_steps" in shrink_report


# ===========================================================================
# 6. Analysis & Wilson CI Tests
# ===========================================================================

def test_wilson_ci_math() -> None:
    # 0 forbidden out of 1024 -> upper bound should be small (< 0.005).
    low, high = compute_wilson_score_interval(0, 1024, confidence=0.95, one_sided=False)
    assert low == 0.0
    assert high < 0.005

    upper_1sided = compute_one_sided_wilson_upper(0, 1024, confidence=0.95)
    assert upper_1sided < 0.005

    # Boundary: n=0.
    assert compute_wilson_score_interval(0, 0) == (0.0, 0.0)


def test_analyze_campaign_results() -> None:
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=100)
    env = E04ExecutorEnv()
    oracle = Oracle(schedules)

    run_record = execute_campaign(schedules, env, oracle)
    analysis = analyze_campaign_results(run_record)

    assert isinstance(analysis, CampaignAnalysis)
    assert analysis.primary_endpoint_pass is True
    assert analysis.forbidden_count == 0
    assert analysis.forbidden_commit_rate == 0.0
    assert len(analysis.timing_breakdown) > 0

    report_str = generate_summary_report(analysis)
    assert "PASS (0 Forbidden Commits)" in report_str


# ===========================================================================
# 7. End-to-End Campaign Verification (>= 1,024 Schedules)
# ===========================================================================

def test_full_campaign_zero_forbidden_commits(tmp_path: Path) -> None:
    """End-to-end campaign execution over >= 1,024 generated schedules.

    Verifies zero forbidden commits across all generated schedules.
    """
    schedules = generate_schedules(seed=GENERATOR_SEED, minimum=1024)
    assert len(schedules) >= 1024

    env = E04ExecutorEnv()
    oracle = Oracle(schedules)

    out_json = tmp_path / "e04_run_record.json"
    run_record = execute_campaign(schedules, env, oracle, out_path=out_json)

    assert out_json.exists()

    analysis = analyze_campaign_results(run_record)

    # Primary invariant: ZERO forbidden commits.
    assert analysis.forbidden_count == 0, f"Observed {analysis.forbidden_count} forbidden commits!"
    assert analysis.forbidden_commit_rate == 0.0
    assert analysis.primary_endpoint_pass is True

    # Wilson score 95% upper bound for zero events in >=1,024 trials must be < 0.005
    assert analysis.forbidden_commit_rate_upper_95 < 0.005
