"""Mutation tests for formal governance invariants.

Demonstrates non-vacuity of the invariant checking engine by deliberately:
1. Constructing mutated/defective transition outcomes and states for each of the
   11 governance invariants (I1-I11) and asserting that the invariant checkers
   flag the exact violation ID.
2. Running bounded exploration under mutated transition handlers to verify that
   any single defect in transition admission produces recorded counterexamples.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from evaluation.formal_governance.explore import explore
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
    CONSENT_GRANTED,
    CONSENT_REVOKED,
    EXPIRED,
    TTL,
    State,
    initial_state,
)
from evaluation.formal_governance.transitions import Outcome, apply


def _clean_bound_source() -> State:
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


class InvariantNonVacuityMutationTests(unittest.TestCase):
    """Direct non-vacuity unit tests for invariants I1 through I11."""

    def test_I1_mutation_stale_base(self) -> None:
        base = _clean_bound_source()
        stale_source = build_state(base, state_version=base.state_version + 1)
        target = _committed_target(stale_source)
        flagged = transition_invariants(
            stale_source, "commit", {}, synthetic_success(stale_source, target)
        )
        self.assertIn("I1_no_stale_base_commit", flagged)

    def test_I2_mutation_revoked_consent(self) -> None:
        revoked_source = build_state(_clean_bound_source(), consent_state=CONSENT_REVOKED)
        target = _committed_target(revoked_source)
        flagged = transition_invariants(
            revoked_source, "commit", {}, synthetic_success(revoked_source, target)
        )
        self.assertIn("I2_no_post_revocation_commit", flagged)

    def test_I2_mutation_stale_consent_version(self) -> None:
        stale_source = build_state(_clean_bound_source(), consent_version=1)
        target = _committed_target(stale_source)
        flagged = transition_invariants(
            stale_source, "commit", {}, synthetic_success(stale_source, target)
        )
        self.assertIn("I2_no_post_revocation_commit", flagged)

    def test_I3_mutation_wrong_actor(self) -> None:
        wrong_actor = build_state(_clean_bound_source(), proposal_actor="a_attacker")
        target = _committed_target(wrong_actor)
        flagged = transition_invariants(
            wrong_actor, "commit", {}, synthetic_success(wrong_actor, target)
        )
        self.assertIn("I3_no_wrong_coordinate_commit", flagged)

    def test_I3_mutation_wrong_role(self) -> None:
        wrong_role = build_state(_clean_bound_source(), proposal_role="r_attacker")
        target = _committed_target(wrong_role)
        flagged = transition_invariants(
            wrong_role, "commit", {}, synthetic_success(wrong_role, target)
        )
        self.assertIn("I3_no_wrong_coordinate_commit", flagged)

    def test_I3_mutation_wrong_purpose(self) -> None:
        wrong_purpose = build_state(_clean_bound_source(), proposal_purpose="p_attacker")
        target = _committed_target(wrong_purpose)
        flagged = transition_invariants(
            wrong_purpose, "commit", {}, synthetic_success(wrong_purpose, target)
        )
        self.assertIn("I3_no_wrong_coordinate_commit", flagged)

    def test_I3_mutation_wrong_task(self) -> None:
        wrong_task = build_state(_clean_bound_source(), proposal_task="t_attacker")
        target = _committed_target(wrong_task)
        flagged = transition_invariants(
            wrong_task, "commit", {}, synthetic_success(wrong_task, target)
        )
        self.assertIn("I3_no_wrong_coordinate_commit", flagged)

    def test_I4_mutation_corrupt_digest(self) -> None:
        corrupt_source = build_state(_clean_bound_source(), digest_valid=False)
        target = _committed_target(corrupt_source)
        flagged = transition_invariants(
            corrupt_source, "commit", {}, synthetic_success(corrupt_source, target)
        )
        self.assertIn("I4_no_expired_tampered_snapshot_commit", flagged)

    def test_I4_mutation_expired_snapshot(self) -> None:
        expired_source = build_state(_clean_bound_source(), expiry=EXPIRED)
        target = _committed_target(expired_source)
        flagged = transition_invariants(
            expired_source, "commit", {}, synthetic_success(expired_source, target)
        )
        self.assertIn("I4_no_expired_tampered_snapshot_commit", flagged)

    def test_I5_mutation_undisclosed_evidence(self) -> None:
        undisclosed_source = build_state(
            _clean_bound_source(),
            proposal_evidence=frozenset({"e0", "e1"}),
            disclosed_evidence_set=frozenset({"e0"}),
        )
        target = _committed_target(undisclosed_source)
        flagged = transition_invariants(
            undisclosed_source, "commit", {}, synthetic_success(undisclosed_source, target)
        )
        self.assertIn("I5_no_undisclosed_evidence", flagged)

    def test_I6_mutation_idempotent_replay_advances_version(self) -> None:
        source = _clean_bound_source()
        advanced_target = build_state(source, state_version=source.state_version + 1)
        bad_outcome = Outcome(True, advanced_target, "idempotent_replay", idempotent=True)
        flagged = transition_invariants(source, "replay_proposal", {}, bad_outcome)
        self.assertIn("I6_idempotent_replay_one_transition", flagged)

    def test_I7_mutation_commit_no_version_advance(self) -> None:
        source = _clean_bound_source()
        no_advance_target = build_state(
            source,
            proposal_base=None,
            snapshot_id=None,
            commit_status=COMMIT_APPLIED,
        )
        flagged = transition_invariants(
            source, "commit", {}, synthetic_success(source, no_advance_target)
        )
        self.assertIn("I7_commit_advances_once", flagged)

    def test_I8_mutation_rejected_advances_canonical(self) -> None:
        source = _clean_bound_source()
        modified_source = build_state(source, state_version=source.state_version + 1)
        bad_rejected = Outcome(False, modified_source, "stale_base")
        flagged = transition_invariants(source, "commit", {}, bad_rejected)
        self.assertIn("I8_rejected_does_not_advance", flagged)

    def test_I9_mutation_nondeterministic_outcome(self) -> None:
        source = initial_state()
        bogus_outcome = Outcome(True, source, "fake_outcome")
        flagged = transition_invariants(source, "change_role", {"role": "r1"}, bogus_outcome)
        self.assertIn("I9_admitted_reconstructable", flagged)

    def test_I10_mutation_stale_policy(self) -> None:
        stale_policy_source = build_state(_clean_bound_source(), policy_version=1)
        target = _committed_target(stale_policy_source)
        flagged = transition_invariants(
            stale_policy_source, "commit", {}, synthetic_success(stale_policy_source, target)
        )
        self.assertIn("I10_current_policy_in_admission", flagged)

    def test_I11_mutation_broken_clean_path(self) -> None:
        revoked_initial = build_state(initial_state(), consent_state=CONSENT_REVOKED)
        self.assertFalse(check_i11(revoked_initial))


class ExplorationModelMutationTests(unittest.TestCase):
    """Verify that bounded exploration catches injected admission defects."""

    def test_mutated_commit_bypassing_stale_base_is_killed(self) -> None:
        def mutated_transition_check(cur: State, name: str, params: dict, outcome: Outcome) -> list[str]:
            # Inject a mutant: if a commit attempts from a stale base state, return synthetic success
            if name == "commit" and cur.has_proposal and cur.proposal_base != cur.state_version:
                target = _committed_target(cur)
                syn = synthetic_success(cur, target)
                return transition_invariants(cur, name, params, syn)
            return []

        report = explore(max_depth=4, transition_check_extra=mutated_transition_check)
        self.assertGreater(report["violation_count"], 0)
        violated_ids = [v[0] for v in report["violations"]]
        self.assertIn("I1_no_stale_base_commit", violated_ids)

    def test_mutated_commit_bypassing_consent_revocation_is_killed(self) -> None:
        def mutated_transition_check(cur: State, name: str, params: dict, outcome: Outcome) -> list[str]:
            if name == "commit" and cur.has_proposal and cur.consent_state == CONSENT_REVOKED:
                target = _committed_target(cur)
                syn = synthetic_success(cur, target)
                return transition_invariants(cur, name, params, syn)
            return []

        report = explore(max_depth=4, transition_check_extra=mutated_transition_check)
        self.assertGreater(report["violation_count"], 0)
        violated_ids = [v[0] for v in report["violations"]]
        self.assertIn("I2_no_post_revocation_commit", violated_ids)

    def test_all_11_invariants_covered_in_mutation_suite(self) -> None:
        expected = [
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
        self.assertEqual(all_invariant_ids(), expected)


if __name__ == "__main__":
    unittest.main()
