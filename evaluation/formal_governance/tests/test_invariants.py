"""Tests for the machine-checkable invariant functions."""

from __future__ import annotations

import unittest

from evaluation.formal_governance.invariants import (
    all_invariant_ids,
    build_state,
    check_i11,
    state_invariants,
    synthetic_success,
    transition_invariants,
)
from evaluation.formal_governance.model import (
    COMMIT_APPLIED,
    CONSENT_REVOKED,
    EXPIRED,
    TTL,
    State,
    initial_state,
)
from evaluation.formal_governance.transitions import Outcome, apply

REQUIRED_INVARIANTS = [
    "I1_no_stale_base_commit",
    "I2_no_post_revocation_commit",
    "I3_no_wrong_coordinate_commit",
    "I4_no_expired_tampered_snapshot_commit",
    "I5_no_undisclosed_evidence",
    "I6_idempotent_replay_one_transition",
    "I7_commit_advances_once",
    "I8_rejected_does_not_advance",
    "I9_admitted_reconstructable",
    "I10_current_policy_in_admission",
    "I11_clean_commit_reachable",
]


def _admissible_bound_source() -> State:
    """A state with a fully current, snapshot-bound proposal."""
    st = apply(initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL).state
    return apply(
        st, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
    ).state


def _committed_target(source: State) -> State:
    return build_state(
        source,
        state_version=source.state_version + 1,
        proposal_base=None,
        snapshot_id=None,
        commit_status=COMMIT_APPLIED,
    )


class StateInvariantTests(unittest.TestCase):
    def test_clean_states_satisfy_all_state_invariants(self) -> None:
        self.assertEqual(state_invariants(initial_state()), [])
        self.assertEqual(state_invariants(_admissible_bound_source()), [])

    def test_flags_bad_vocab(self) -> None:
        st = build_state(initial_state(), consent_state="weird", commit_status="bogus", origin="nope")
        flagged = state_invariants(st)
        self.assertIn("vocab_consent_state", flagged)
        self.assertIn("vocab_commit_status", flagged)
        self.assertIn("vocab_origin", flagged)

    def test_flags_version_and_expiry_domain(self) -> None:
        st = build_state(initial_state(), state_version=-1, policy_version=9, consent_version=-2, expiry=42)
        flagged = state_invariants(st)
        self.assertIn("version_state_in_domain", flagged)
        self.assertIn("version_policy_in_domain", flagged)
        self.assertIn("version_consent_in_domain", flagged)
        self.assertIn("expiry_in_domain", flagged)

    def test_flags_commit_leaves_proposal_or_snapshot(self) -> None:
        st = build_state(_admissible_bound_source(), commit_status=COMMIT_APPLIED)
        flagged = state_invariants(st)
        self.assertIn("commit_applied_consumes_proposal", flagged)
        self.assertIn("commit_applied_consumes_snapshot", flagged)

    def test_flags_digest_without_snapshot(self) -> None:
        st = build_state(initial_state(), digest_valid=False)
        self.assertIn("digest_consistent", state_invariants(st))

    def test_flags_evidence_outside_universe(self) -> None:
        st = build_state(initial_state(), proposal_evidence=frozenset({"zx"}), disclosed_evidence_set=frozenset({"zz"}))
        flagged = state_invariants(st)
        self.assertIn("evidence_in_universe", flagged)
        self.assertIn("disclosed_in_universe", flagged)


class TransitionInvariantTests(unittest.TestCase):
    def test_no_violations_for_clean_commit(self) -> None:
        source = _admissible_bound_source()
        outcome = apply(source, "commit")
        self.assertTrue(outcome.admitted)
        self.assertEqual(transition_invariants(source, "commit", {}, outcome), [])

    def test_I1_stale_base_bound_commit(self) -> None:
        base = _admissible_bound_source()
        source = build_state(base, state_version=base.state_version + 1)
        target = _committed_target(source)
        flagged = transition_invariants(source, "commit", {}, synthetic_success(source, target))
        self.assertIn("I1_no_stale_base_commit", flagged)

    def test_I2_post_revocation_commit(self) -> None:
        source = build_state(_admissible_bound_source(), consent_state=CONSENT_REVOKED)
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, _committed_target(source))
        )
        self.assertIn("I2_no_post_revocation_commit", flagged)

    def test_I2_stale_consent_version_commit(self) -> None:
        source = build_state(_admissible_bound_source(), consent_version=1)
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, _committed_target(source))
        )
        self.assertIn("I2_no_post_revocation_commit", flagged)

    def test_I3_wrong_coordinate_commit(self) -> None:
        for field_name, wrong in (("actor", "a9"), ("role", "r9"), ("purpose", "p9"), ("task", "t9")):
            source = build_state(_admissible_bound_source(), **{f"proposal_{field_name}": wrong})
            flagged = transition_invariants(
                source, "commit", {}, synthetic_success(source, _committed_target(source))
            )
            self.assertIn("I3_no_wrong_coordinate_commit", flagged)

    def test_I4_corrupt_digest_commit(self) -> None:
        source = build_state(_admissible_bound_source(), digest_valid=False)
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, _committed_target(source))
        )
        self.assertIn("I4_no_expired_tampered_snapshot_commit", flagged)

    def test_I4_expired_snapshot_commit(self) -> None:
        source = build_state(_admissible_bound_source(), expiry=EXPIRED)
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, _committed_target(source))
        )
        self.assertIn("I4_no_expired_tampered_snapshot_commit", flagged)

    def test_I5_undisclosed_evidence_commit(self) -> None:
        source = build_state(
            _admissible_bound_source(),
            proposal_evidence=frozenset({"e0", "e1"}),
            disclosed_evidence_set=frozenset({"e0"}),
        )
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, _committed_target(source))
        )
        self.assertIn("I5_no_undisclosed_evidence", flagged)

    def test_I7_commit_advances_exactly_once(self) -> None:
        source = _admissible_bound_source()
        target = _committed_target(source)
        wrong_target = build_state(target, state_version=source.state_version)  # did not advance
        flagged = transition_invariants(source, "commit", {}, synthetic_success(source, wrong_target))
        self.assertIn("I7_commit_advances_once", flagged)

    def test_I10_stale_policy_commit(self) -> None:
        source = build_state(_admissible_bound_source(), policy_version=1)
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, _committed_target(source))
        )
        self.assertIn("I10_current_policy_in_admission", flagged)

    def test_I6_idempotent_replay_must_not_advance(self) -> None:
        source = _admissible_bound_source()
        changed = build_state(source, state_version=source.state_version + 1)
        outcome = Outcome(True, changed, "idempotent_replay", idempotent=True)
        flagged = transition_invariants(source, "replay_proposal", {}, outcome)
        self.assertIn("I6_idempotent_replay_one_transition", flagged)

    def test_I8_rejected_must_not_advance_canonical(self) -> None:
        source = _admissible_bound_source()
        changed = build_state(source, state_version=source.state_version + 1)
        outcome = Outcome(False, changed, "stale_base")
        flagged = transition_invariants(source, "commit", {}, outcome)
        self.assertIn("I8_rejected_does_not_advance", flagged)

    def test_I9_admitted_transition_reconstructable(self) -> None:
        source = initial_state()
        params = {"role": "r1"}
        wrong = Outcome(True, source, "bogus")  # differs from apply(source, change_role)
        flagged = transition_invariants(source, "change_role", params, wrong)
        self.assertIn("I9_admitted_reconstructable", flagged)


class PositivePropertyTests(unittest.TestCase):
    def test_I11_clean_commit_reachable(self) -> None:
        self.assertTrue(check_i11(initial_state()))
        self.assertTrue(apply(initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL).admitted)


class InventoryTests(unittest.TestCase):
    def test_all_invariant_ids_match_required_list(self) -> None:
        self.assertEqual(all_invariant_ids(), REQUIRED_INVARIANTS)


if __name__ == "__main__":
    unittest.main()
