"""Unit tests for the canonical state model and its transitions."""

from __future__ import annotations

import unittest
from dataclasses import replace

from evaluation.formal_governance.model import (
    COMMIT_APPLIED,
    COMMIT_NONE,
    COMMIT_REJECTED,
    CONSENT_GRANTED,
    EXPIRED,
    MAX_VERSION,
    TTL,
    State,
    bump_version,
    initial_state,
    snapshot_digest,
)
from evaluation.formal_governance.transitions import (
    TRANSITION_NAMES,
    apply,
)


class BumpVersionTests(unittest.TestCase):
    def test_increments_below_cap(self) -> None:
        self.assertEqual(bump_version(0), 1)

    def test_saturates_at_cap(self) -> None:
        self.assertEqual(bump_version(MAX_VERSION), MAX_VERSION)


class SnapshotDigestTests(unittest.TestCase):
    def test_deterministic(self) -> None:
        st = initial_state()
        d1 = snapshot_digest(st, evidence=frozenset({"e0"}), expiry=TTL)
        d2 = snapshot_digest(st, evidence=frozenset({"e0"}), expiry=TTL)
        self.assertEqual(d1, d2)
        self.assertEqual(len(d1), 64)

    def test_sensitive_to_coordinates(self) -> None:
        st = initial_state()
        base = snapshot_digest(st, evidence=frozenset({"e0"}), expiry=TTL)
        self.assertNotEqual(base, snapshot_digest(st, evidence=frozenset({"e0", "e1"}), expiry=TTL))
        advanced = apply(st, "advance_state").state
        self.assertNotEqual(base, snapshot_digest(advanced, evidence=frozenset({"e0"}), expiry=TTL))


class InitialStateTests(unittest.TestCase):
    def test_defaults(self) -> None:
        st = initial_state()
        self.assertEqual(st.subject, "s0")
        self.assertEqual(st.actor, "a0")
        self.assertEqual(st.role, "r0")
        self.assertEqual(st.purpose, "p0")
        self.assertEqual(st.task, "t0")
        self.assertEqual(st.state_version, 0)
        self.assertEqual(st.policy_version, 0)
        self.assertEqual(st.consent_version, 0)
        self.assertEqual(st.consent_state, CONSENT_GRANTED)
        self.assertIsNone(st.snapshot_id)
        self.assertTrue(st.digest_valid)
        self.assertIsNone(st.expiry)
        self.assertEqual(st.disclosed_evidence_set, frozenset())
        self.assertIsNone(st.proposal_base)
        self.assertFalse(st.proposal_binding)
        self.assertEqual(st.committed_keys, frozenset())
        self.assertEqual(st.commit_status, COMMIT_NONE)


class DisclosureTests(unittest.TestCase):
    def test_issue_disclosure_creates_snapshot(self) -> None:
        outcome = apply(initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL)
        self.assertTrue(outcome.admitted)
        st = outcome.state
        self.assertIsNotNone(st.snapshot_id)
        self.assertTrue(st.digest_valid)
        self.assertEqual(st.expiry, TTL)
        self.assertEqual(st.disclosed_evidence_set, frozenset({"e0"}))

    def test_issue_disclosure_rejected_after_revocation(self) -> None:
        st = apply(initial_state(), "revoke_consent").state
        outcome = apply(st, "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL)
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "consent_revoked")


class ProposalTests(unittest.TestCase):
    def test_unbound_proposal_records_coordinates(self) -> None:
        st = apply(initial_state(), "create_proposal", binding=False, idempotency_key="k0").state
        self.assertEqual(st.proposal_base, 0)
        self.assertFalse(st.proposal_binding)
        self.assertEqual(st.proposal_actor, "a0")
        self.assertEqual(st.proposal_role, "r0")
        self.assertEqual(st.proposal_purpose, "p0")
        self.assertEqual(st.proposal_task, "t0")
        self.assertEqual(st.proposal_policy_version, 0)
        self.assertEqual(st.proposal_consent_version, 0)
        self.assertEqual(st.idempotency_key, "k0")

    def test_bound_proposal_requires_valid_disclosure(self) -> None:
        outcome = apply(initial_state(), "create_proposal", binding=True, idempotency_key="k0")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "no_valid_disclosure")

    def test_bound_proposal_rejects_undisclosed_evidence(self) -> None:
        st = apply(
            initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL
        ).state
        outcome = apply(
            st, "create_proposal", binding=True, evidence=frozenset({"e1"}), idempotency_key="k0"
        )
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "evidence_not_disclosed")


class CommitTests(unittest.TestCase):
    def _clean_bound(self) -> State:
        st = apply(
            initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL
        ).state
        st = apply(
            st, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
        ).state
        return st

    def test_commit_admitted_advances_version_once(self) -> None:
        st = self._clean_bound()
        outcome = apply(st, "commit")
        self.assertTrue(outcome.admitted)
        self.assertFalse(outcome.idempotent)
        self.assertEqual(outcome.reason, "committed")
        self.assertEqual(outcome.state.state_version, st.state_version + 1)
        self.assertEqual(outcome.state.commit_status, COMMIT_APPLIED)
        self.assertIn("k0", outcome.state.committed_keys)

    def test_commit_consumes_proposal_and_snapshot(self) -> None:
        st = self._clean_bound()
        outcome = apply(st, "commit")
        self.assertIsNone(outcome.state.proposal_base)
        self.assertIsNone(outcome.state.snapshot_id)
        self.assertEqual(outcome.state.disclosed_evidence_set, frozenset())

    def test_commit_stale_base_rejected(self) -> None:
        st = apply(self._clean_bound(), "advance_state").state
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "stale_base")
        self.assertEqual(outcome.state.state_version, st.state_version)
        self.assertEqual(outcome.state.commit_status, COMMIT_REJECTED)

    def test_commit_post_revocation_rejected(self) -> None:
        st = apply(self._clean_bound(), "revoke_consent").state
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "consent_revoked")

    def test_commit_wrong_role_rejected(self) -> None:
        st = apply(self._clean_bound(), "change_role", role="r1").state
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "role_mismatch")

    def test_commit_wrong_purpose_rejected(self) -> None:
        st = apply(self._clean_bound(), "change_purpose", purpose="p1").state
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "purpose_mismatch")

    def test_commit_expired_snapshot_rejected(self) -> None:
        st = apply(self._clean_bound(), "expire_snapshot").state
        self.assertEqual(st.expiry, EXPIRED)
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "snapshot_expired")

    def test_commit_corrupt_digest_rejected(self) -> None:
        st = apply(self._clean_bound(), "corrupt_digest").state
        self.assertFalse(st.digest_valid)
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "corrupt_digest")

    def test_commit_undisclosed_evidence_rejected(self) -> None:
        # A bound proposal can never be created with undisclosed evidence, so
        # build the adversarial state directly to exercise the commit-time gate.
        st = self._clean_bound()
        st = replace(st, proposal_evidence=frozenset({"e0", "e1"}))
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "evidence_not_disclosed")

    def test_commit_stale_policy_rejected(self) -> None:
        st = apply(self._clean_bound(), "advance_policy").state
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "stale_policy")

    def test_commit_no_proposal_rejected(self) -> None:
        outcome = apply(initial_state(), "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "no_proposal")


class ReplayAndRetryTests(unittest.TestCase):
    def test_idempotent_replay_is_one_logical_transition(self) -> None:
        st = apply(
            initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL
        ).state
        st = apply(
            st, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
        ).state
        first = apply(st, "commit")
        self.assertTrue(first.admitted)
        self.assertEqual(first.state.state_version, st.state_version + 1)
        # Client resends the same proposal with the same key after a success.
        st2 = apply(first.state, "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL).state
        st2 = apply(
            st2, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
        ).state
        replay = apply(st2, "replay_proposal")
        self.assertTrue(replay.admitted)
        self.assertTrue(replay.idempotent)
        self.assertEqual(replay.reason, "idempotent_replay")
        self.assertEqual(replay.state, st2)
        self.assertEqual(replay.state.state_version, st2.state_version)

    def test_retry_after_rejection_stays_rejected_without_reauthorization(self) -> None:
        st = apply(
            initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL
        ).state
        st = apply(
            st, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
        ).state
        st = apply(st, "advance_state").state
        rejected = apply(st, "commit")
        self.assertFalse(rejected.admitted)
        self.assertEqual(rejected.reason, "stale_base")
        retried = apply(rejected.state, "retry")
        self.assertFalse(retried.admitted)
        self.assertEqual(retried.reason, "stale_base")
        self.assertEqual(retried.state.state_version, rejected.state.state_version)

    def test_retry_requires_prior_rejection(self) -> None:
        st = apply(initial_state(), "create_proposal", binding=False).state
        outcome = apply(st, "retry")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "nothing_to_retry")


class RollbackTests(unittest.TestCase):
    def _committed(self) -> State:
        st = apply(
            initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL
        ).state
        st = apply(
            st, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
        ).state
        return apply(st, "commit").state

    def test_rollback_only_after_applied_commit(self) -> None:
        outcome = apply(initial_state(), "rollback")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.reason, "nothing_to_rollback")

    def test_rollback_reverts_version(self) -> None:
        committed = self._committed()
        outcome = apply(committed, "rollback")
        self.assertTrue(outcome.admitted)
        self.assertEqual(outcome.state.state_version, committed.state_version - 1)
        self.assertEqual(outcome.state.commit_status, "rolled_back")


class DispatchTests(unittest.TestCase):
    def test_all_defined_transitions_dispatchable(self) -> None:
        expected = {
            "issue_disclosure",
            "create_proposal",
            "advance_state",
            "revoke_consent",
            "change_role",
            "change_purpose",
            "advance_policy",
            "expire_snapshot",
            "corrupt_digest",
            "replay_proposal",
            "commit",
            "retry",
            "rollback",
        }
        self.assertEqual(TRANSITION_NAMES, frozenset(expected))
        st = initial_state()
        for name in sorted(expected):
            params: dict[str, object] = {}
            if name == "change_role":
                params = {"role": "r1"}
            elif name == "change_purpose":
                params = {"purpose": "p1"}
            elif name == "issue_disclosure":
                params = {"evidence": frozenset({"e0"}), "expiry": TTL}
            elif name == "create_proposal":
                params = {"binding": False, "evidence": frozenset(), "idempotency_key": "k0"}
            apply(st, name, **params)

    def test_unknown_transition_raises(self) -> None:
        with self.assertRaises(ValueError):
            apply(initial_state(), "no_such_transition")


class CanonicalPreservationTests(unittest.TestCase):
    def test_rejected_commit_preserves_canonical_coordinates(self) -> None:
        st = apply(
            initial_state(), "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL
        ).state
        st = apply(
            st, "create_proposal", binding=True, evidence=frozenset({"e0"}), idempotency_key="k0"
        ).state
        st = apply(st, "advance_state").state
        outcome = apply(st, "commit")
        self.assertFalse(outcome.admitted)
        self.assertEqual(outcome.state.canonical, st.canonical)
        self.assertNotEqual(outcome.state.commit_status, st.commit_status)


if __name__ == "__main__":
    unittest.main()
