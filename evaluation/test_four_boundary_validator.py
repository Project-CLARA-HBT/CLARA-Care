"""Tests for Santos-Grueiro 4-Boundary Commit-Time Authorization Framework."""

import pytest

from evaluation.four_boundary_validator import (
    AuthorizationLease,
    BitemporalInterval,
    BoundaryViolationType,
    ClinicalMutation,
    EntityDAGCoordinate,
    SantosGrueiroFourBoundaryValidator,
    run_four_boundary_stress_evaluation,
)


@pytest.fixture
def validator() -> SantosGrueiroFourBoundaryValidator:
    return SantosGrueiroFourBoundaryValidator()


@pytest.fixture
def base_context():
    t0 = 1000.0
    profile = "patient-test-01"
    c_met = EntityDAGCoordinate(profile, "medication", "metformin")
    c_lis = EntityDAGCoordinate(profile, "medication", "lisinopril")

    lease = AuthorizationLease(
        lease_id="lease-001",
        profile_id=profile,
        actor_id="dr_smith",
        actor_role="physician",
        purpose="treatment",
        authorized_coordinates={c_met.to_key(), c_lis.to_key()},
        snapshot_base_versions={c_met.to_key(): 1, c_lis.to_key(): 2},
        policy_epoch=1,
        consent_epoch=1,
        issued_at=t0,
        expires_at=t0 + 60.0,
    )

    interval = BitemporalInterval(
        valid_start=t0 - 50,
        valid_end=None,
        know_start=t0 - 50,
        know_end=None,
    )

    mutation = ClinicalMutation(
        coordinate=c_met,
        action="update",
        payload={"drug_name": "metformin", "dose": "500mg"},
        temporal_validity=interval,
        claimed_base_version=1,
    )

    return {
        "t0": t0,
        "profile": profile,
        "c_met": c_met,
        "c_lis": c_lis,
        "lease": lease,
        "interval": interval,
        "mutation": mutation,
        "committed_versions": {c_met.to_key(): 1, c_lis.to_key(): 2},
    }


def test_valid_proposal_passes_all_boundaries(validator, base_context):
    ctx = base_context
    res = validator.evaluate_proposal(
        lease=ctx["lease"],
        mutations=[ctx["mutation"]],
        committed_partition_versions=ctx["committed_versions"],
        current_active_medications={"lisinopril"},
        current_policy_epoch=1,
        current_consent_epoch=1,
        current_time=ctx["t0"] + 10.0,
    )
    assert res.is_admissible is True
    assert res.primary_violation == BoundaryViolationType.NONE
    assert res.freshness_passed is True
    assert res.causal_precedence_passed is True
    assert res.effect_scoping_passed is True
    assert res.admissibility_passed is True


def test_freshness_boundary_blocks_expired_lease(validator, base_context):
    ctx = base_context
    res = validator.evaluate_proposal(
        lease=ctx["lease"],
        mutations=[ctx["mutation"]],
        committed_partition_versions=ctx["committed_versions"],
        current_active_medications={"lisinopril"},
        current_policy_epoch=1,
        current_consent_epoch=1,
        current_time=ctx["t0"] + 100.0,  # Expired
    )
    assert res.is_admissible is False
    assert res.primary_violation == BoundaryViolationType.FRESHNESS_VIOLATION
    assert res.freshness_passed is False


def test_causal_precedence_boundary_blocks_stale_base_version(validator, base_context):
    ctx = base_context
    # Advance DB version to 2
    versions = {ctx["c_met"].to_key(): 2, ctx["c_lis"].to_key(): 2}
    res = validator.evaluate_proposal(
        lease=ctx["lease"],
        mutations=[ctx["mutation"]],
        committed_partition_versions=versions,
        current_active_medications={"lisinopril"},
        current_policy_epoch=1,
        current_consent_epoch=1,
        current_time=ctx["t0"] + 10.0,
    )
    assert res.is_admissible is False
    assert res.primary_violation == BoundaryViolationType.CAUSAL_PRECEDENCE_VIOLATION
    assert res.causal_precedence_passed is False


def test_effect_scoping_boundary_blocks_unauthorized_coordinate(validator, base_context):
    ctx = base_context
    unauth_coord = EntityDAGCoordinate(ctx["profile"], "medication", "insulin")
    unauth_mut = ClinicalMutation(
        coordinate=unauth_coord,
        action="insert",
        payload={"drug_name": "insulin"},
        temporal_validity=ctx["interval"],
        claimed_base_version=1,
    )
    res = validator.evaluate_proposal(
        lease=ctx["lease"],
        mutations=[unauth_mut],
        committed_partition_versions=ctx["committed_versions"],
        current_active_medications={"lisinopril"},
        current_policy_epoch=1,
        current_consent_epoch=1,
        current_time=ctx["t0"] + 10.0,
    )
    assert res.is_admissible is False
    assert res.primary_violation == BoundaryViolationType.EFFECT_SCOPING_VIOLATION
    assert res.effect_scoping_passed is False


def test_admissibility_boundary_blocks_severe_ddi(validator, base_context):
    ctx = base_context
    c_war = EntityDAGCoordinate(ctx["profile"], "medication", "warfarin")
    lease = ctx["lease"]
    lease.authorized_coordinates.add(c_war.to_key())
    lease.snapshot_base_versions[c_war.to_key()] = 1

    war_mut = ClinicalMutation(
        coordinate=c_war,
        action="insert",
        payload={"drug_name": "warfarin"},
        temporal_validity=ctx["interval"],
        claimed_base_version=1,
    )

    # Co-prescribing Warfarin when patient is on Aspirin
    res = validator.evaluate_proposal(
        lease=lease,
        mutations=[war_mut],
        committed_partition_versions={**ctx["committed_versions"], c_war.to_key(): 1},
        current_active_medications={"aspirin"},
        current_policy_epoch=1,
        current_consent_epoch=1,
        current_time=ctx["t0"] + 10.0,
    )
    assert res.is_admissible is False
    assert res.primary_violation == BoundaryViolationType.ADMISSIBILITY_VIOLATION
    assert res.admissibility_passed is False
    assert (
        "warfarin + aspirin" in res.ddi_conflicts_detected
        or "aspirin + warfarin" in res.ddi_conflicts_detected
    )


def test_admissibility_boundary_blocks_consent_revocation(validator, base_context):
    ctx = base_context
    res = validator.evaluate_proposal(
        lease=ctx["lease"],
        mutations=[ctx["mutation"]],
        committed_partition_versions=ctx["committed_versions"],
        current_active_medications={"lisinopril"},
        current_policy_epoch=1,
        current_consent_epoch=2,  # Consent epoch advanced / revoked
        current_time=ctx["t0"] + 10.0,
    )
    assert res.is_admissible is False
    assert res.primary_violation == BoundaryViolationType.ADMISSIBILITY_VIOLATION
    assert res.admissibility_passed is False


def test_stress_evaluation_100_percent_pass():
    report = run_four_boundary_stress_evaluation(50)
    assert report["all_boundaries_enforced"] is True
    assert report["clean_acceptance_rate"] == 1.0
    assert report["freshness_block_rate"] == 1.0
    assert report["causal_block_rate"] == 1.0
    assert report["scoping_block_rate"] == 1.0
    assert report["admissibility_block_rate"] == 1.0
