from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from evaluation.property_assurance.toy_governed_store import (
    ToyGovernanceError,
    ToyGovernedStore,
)


@pytest.fixture()
def governed_store() -> ToyGovernedStore:
    return ToyGovernedStore(subject="synthetic-subject", actor="actor-a", purpose="research")


def test_commit_revalidates_each_governance_coordinate() -> None:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    for expected_error in (
        "snapshot_state_version_mismatch",
        "snapshot_policy_version_mismatch",
        "snapshot_consent_version_mismatch",
        "snapshot_actor_mismatch",
        "snapshot_purpose_mismatch",
    ):
        store = ToyGovernedStore(subject="synthetic-subject", actor="actor-a", purpose="research")
        snapshot = store.issue_snapshot(now=now)
        proposal = store.propose(proposal_id=f"proposal-{expected_error}", snapshot=snapshot)
        if expected_error == "snapshot_state_version_mismatch":
            store.change_state()
        elif expected_error == "snapshot_policy_version_mismatch":
            store.change_policy()
        elif expected_error == "snapshot_consent_version_mismatch":
            store.change_consent()
        elif expected_error == "snapshot_actor_mismatch":
            store.change_actor("actor-b")
        else:
            store.change_purpose("other-purpose")
        with pytest.raises(ToyGovernanceError, match=expected_error):
            store.commit(proposal=proposal, now=now)


def test_commit_is_idempotent_and_expired_snapshot_is_rejected(governed_store: ToyGovernedStore) -> None:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    snapshot = governed_store.issue_snapshot(now=now)
    proposal = governed_store.propose(proposal_id="retry", snapshot=snapshot)
    assert governed_store.commit(proposal=proposal, now=now) == 1
    assert governed_store.commit(proposal=proposal, now=now + timedelta(minutes=1)) == 1

    expired = governed_store.issue_snapshot(now=now)
    with pytest.raises(ToyGovernanceError, match="snapshot_expired"):
        governed_store.commit(
            proposal=governed_store.propose(proposal_id="expired", snapshot=expired),
            now=expired.expires_at,
        )
