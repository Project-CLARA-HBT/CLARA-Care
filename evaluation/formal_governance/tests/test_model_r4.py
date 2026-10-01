"""Tests for R4 Formal Governance Model and Invariants (I16–I24)."""

import pytest
from evaluation.formal_governance.model_r4 import (
    R4Binding,
    R4Proposal,
    R4State,
    check_r4_invariants,
    evaluate_c0,
    evaluate_c1,
    evaluate_c2,
    evaluate_c3,
    evaluate_c4,
)


def test_r4_formal_invariants_hold():
    binding = R4Binding(
        public_id="b1",
        status="COMPLETED",
        snapshot_version=1,
        consent_epoch=1,
        policy_epoch=1,
        disclosed_evidence=("e0", "e1"),
        h_proj="hash_e0_e1",
        h_sem="hash_sem_1",
        h_trans="hash_trans_1",
        attestation_level="L1_TRANSPORT",
    )
    # Good proposal
    p_good = R4Proposal(
        proposal_id="p1",
        binding_id="b1",
        base_state_version=1,
        consent_epoch=1,
        policy_epoch=1,
        asserted_evidence=("e0",),
        observed_projection="hash_e0_e1",
    )
    # Substituted proposal (I16 witness)
    p_sub = R4Proposal(
        proposal_id="p2",
        binding_id="b1",
        base_state_version=1,
        consent_epoch=1,
        policy_epoch=1,
        asserted_evidence=("e0",),
        observed_projection="hash_substituted",
    )
    # Undisclosed evidence proposal (I17 witness)
    p_undisclosed = R4Proposal(
        proposal_id="p3",
        binding_id="b1",
        base_state_version=1,
        consent_epoch=1,
        policy_epoch=1,
        asserted_evidence=("e0", "e2"),  # e2 is in DB but not in b1 disclosed_evidence
        observed_projection="hash_e0_e1",
    )

    state = R4State(
        db_state_version=1,
        db_consent_epoch=1,
        db_policy_epoch=1,
        db_evidence=("e0", "e1", "e2"),
        bindings=(binding,),
        proposals=(p_good, p_sub, p_undisclosed),
    )

    # Invariants should have 0 violations
    violations = check_r4_invariants(state)
    assert violations == []

    # C0 and C1 falsely admit p_sub (blindness)
    assert evaluate_c0(state, p_sub) is True
    assert evaluate_c1(state, p_sub) is True
    # C3 and C4 strictly reject p_sub
    assert evaluate_c3(state, p_sub) is False
    assert evaluate_c4(state, p_sub) is False

    # C1 falsely admits p_undisclosed (blindness)
    assert evaluate_c1(state, p_undisclosed) is True
    # C3 and C4 strictly reject p_undisclosed
    assert evaluate_c3(state, p_undisclosed) is False
    assert evaluate_c4(state, p_undisclosed) is False

    # Clean proposal admitted by all
    assert evaluate_c0(state, p_good) is True
    assert evaluate_c1(state, p_good) is True
    assert evaluate_c2(state, p_good) is True
    assert evaluate_c3(state, p_good) is True
    assert evaluate_c4(state, p_good) is True
