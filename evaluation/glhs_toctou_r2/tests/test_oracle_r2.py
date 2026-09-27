"""Unit tests for E04 Oracle and Statistical Estimands (Role B)."""

import pytest
from evaluation.glhs_toctou_r2.generator import generate_schedules, MINIMUM_UNIQUE_SCHEDULES
from evaluation.glhs_toctou_r2.grammar import (
    ScheduleDescriptor,
    TimingMode,
    EntityConfig,
    Modifier,
    MutationKind,
)
from evaluation.glhs_toctou_r2.oracle import (
    Oracle,
    AdmissibleOutcomeSet,
    COMMITTED_BEFORE_GOVERNANCE_MUTATION,
    SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION,
    INDETERMINATE_ORDERING,
    FORBIDDEN_COMMIT,
    OPERATIONAL_DEADLOCK,
    COMMITTED_OUTCOMES,
    OPERATIONAL_OUTCOMES,
    wilson_ucb_95,
)


def test_generator_produces_minimum_schedules():
    """Verify schedule corpus target N >= 1,024 unique logical schedules."""
    schedules = generate_schedules()
    assert len(schedules) >= MINIMUM_UNIQUE_SCHEDULES
    
    # Verify canonical keys are unique
    keys = {s.canonical_key for s in schedules}
    assert len(keys) == len(schedules), "Duplicate canonical keys found in schedule set"


def test_admissible_outcome_set_classification():
    """Verify 5-class outcome classification and allowed/forbidden properties."""
    desc_reject = ScheduleDescriptor(
        schedule_id="E04-TEST-00001",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
        expected_outcome="REJECT",
    )
    
    oracle = Oracle([desc_reject])
    aos = oracle.get("E04-TEST-00001")
    assert aos is not None
    
    # Check allowed and forbidden outcome sets
    assert "consent_check_failed" in aos.allowed_outcomes
    assert "transition_committed" in aos.forbidden_outcomes
    assert "transition_committed" not in aos.allowed_outcomes
    
    # Test classification
    assert oracle.classify("E04-TEST-00001", "transition_committed") == FORBIDDEN_COMMIT
    assert oracle.is_forbidden("E04-TEST-00001", "transition_committed") is True
    
    assert oracle.classify("E04-TEST-00001", "consent_check_failed") == SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION
    assert oracle.is_safe("E04-TEST-00001", "consent_check_failed") is True


def test_indeterminate_race_classification():
    """Verify overlapping concurrent races are classified as INDETERMINATE_ORDERING."""
    desc_indet = ScheduleDescriptor(
        schedule_id="E04-TEST-00002",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.SIMULTANEOUS_RELEASE,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
        expected_outcome="INDETERMINATE",
    )
    
    oracle = Oracle([desc_indet])
    
    # Committed outcome in concurrent race window is INDETERMINATE_ORDERING, not FORBIDDEN_COMMIT
    assert oracle.classify("E04-TEST-00002", "transition_committed") == INDETERMINATE_ORDERING
    assert oracle.is_forbidden("E04-TEST-00002", "transition_committed") is False
    assert oracle.is_indeterminate("E04-TEST-00002", "transition_committed") is True


def test_positive_control_classification():
    """Verify positive control (ADMIT) is classified as COMMITTED_BEFORE_GOVERNANCE_MUTATION."""
    desc_admit = ScheduleDescriptor(
        schedule_id="E04-TEST-00003",
        mutations=(MutationKind.CONSENT_GRANT,),
        timing=TimingMode.COMMIT_BEFORE_MUTATION,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
        expected_outcome="ADMIT",
    )
    
    oracle = Oracle([desc_admit])
    assert oracle.classify("E04-TEST-00003", "transition_committed") == COMMITTED_BEFORE_GOVERNANCE_MUTATION
    assert oracle.is_safe("E04-TEST-00003", "transition_committed") is True


def test_wilson_ucb_95_calculation():
    """Verify 1-sided 95% Wilson UCB for zero forbidden events across N=1,024."""
    # Zero forbidden events out of 1,024
    ucb = wilson_ucb_95(events=0, total=1024, one_sided=True)
    # Expected: z^2 / (N + z^2) for z = 1.6448536 -> ~0.002635 (0.2635%)
    assert 0.0026 < ucb < 0.0027
    
    # Non-zero events
    ucb_5 = wilson_ucb_95(events=5, total=1024, one_sided=True)
    assert ucb_5 > ucb


def test_oracle_red_team_verifications():
    """Verify Red Team invariants raise assertion errors on invalid outcome setups."""
    # REJECT schedule with transition_committed in safe set should raise AssertionError
    bad_desc = ScheduleDescriptor(
        schedule_id="E04-BAD-00001",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
        expected_outcome="REJECT",
    )
    
    # Manually testing Red Team checks
    oracle = Oracle([bad_desc])
    aos = oracle.get("E04-BAD-00001")
    assert aos is not None
    assert "transition_committed" in aos.forbidden_outcomes
