"""Deterministic transition functions over the canonical state model.

Every transition is a pure function ``State x params -> Outcome``.  An outcome
is either *admitted* (the transition is applied and yields a new state) or
*rejected* (the canonical coordinates are preserved and a reason is recorded).

A commit is the only transition that advances ``state_version``.  It is gated
by the full admission predicate ``_admission_failure``; a failed commit records
``commit_status=rejected`` without touching the canonical coordinates, so a
later ``retry`` re-runs the same admission checks and can never turn a
stale/governance-invalid proposal into an unauthorized success.

Idempotent replays (a proposal whose idempotency key was already applied) are
admitted transitions that return the source state unchanged and never advance
the version.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .model import (
    COMMIT_APPLIED,
    COMMIT_NONE,
    COMMIT_REJECTED,
    COMMIT_ROLLED_BACK,
    CONSENT_GRANTED,
    CONSENT_REVOKED,
    EXPIRED,
    TTL,
    State,
    bump_version,
    snapshot_digest,
)


@dataclass(frozen=True)
class Outcome:
    """Result of applying one transition to a state."""

    admitted: bool
    state: State
    reason: str
    idempotent: bool = False


def issue_disclosure(state: State, *, evidence: frozenset[str] = frozenset(), expiry: int = TTL) -> Outcome:
    if state.consent_state != CONSENT_GRANTED:
        return Outcome(False, state, "consent_revoked")
    ev = frozenset(evidence)
    nxt = replace(
        state,
        snapshot_id=snapshot_digest(state, evidence=ev, expiry=expiry),
        digest_valid=True,
        expiry=expiry,
        disclosed_evidence_set=ev,
        proposal_base=None,
        proposal_binding=False,
        proposal_evidence=frozenset(),
        proposal_actor=None,
        proposal_role=None,
        proposal_purpose=None,
        proposal_task=None,
        proposal_policy_version=None,
        proposal_consent_version=None,
        origin="disclosure",
        idempotency_key=None,
        commit_status=COMMIT_NONE,
    )
    return Outcome(True, nxt, "disclosure_issued")


def create_proposal(
    state: State,
    *,
    binding: bool = False,
    evidence: frozenset[str] = frozenset(),
    idempotency_key: str | None = None,
) -> Outcome:
    ev = frozenset(evidence)
    if binding and not state.snapshot_alive:
        return Outcome(False, state, "no_valid_disclosure")
    if binding and not ev <= state.disclosed_evidence_set:
        return Outcome(False, state, "evidence_not_disclosed")
    nxt = replace(
        state,
        proposal_base=state.state_version,
        proposal_binding=binding,
        proposal_evidence=ev,
        proposal_actor=state.actor,
        proposal_role=state.role,
        proposal_purpose=state.purpose,
        proposal_task=state.task,
        proposal_policy_version=state.policy_version,
        proposal_consent_version=state.consent_version,
        origin="proposal",
        idempotency_key=idempotency_key,
        commit_status=COMMIT_NONE,
    )
    return Outcome(True, nxt, "proposal_created")


def advance_state(state: State) -> Outcome:
    return Outcome(
        True,
        replace(state, state_version=bump_version(state.state_version), origin="state"),
        "state_advanced",
    )


def advance_policy(state: State) -> Outcome:
    return Outcome(
        True,
        replace(state, policy_version=bump_version(state.policy_version), origin="policy"),
        "policy_advanced",
    )


def revoke_consent(state: State) -> Outcome:
    if state.consent_state == CONSENT_REVOKED:
        return Outcome(False, state, "consent_already_revoked")
    return Outcome(
        True,
        replace(
            state,
            consent_version=bump_version(state.consent_version),
            consent_state=CONSENT_REVOKED,
            origin="consent",
        ),
        "consent_revoked",
    )


def change_role(state: State, *, role: str) -> Outcome:
    if role == state.role:
        return Outcome(False, state, "unchanged")
    return Outcome(True, replace(state, role=role, origin="role"), "role_changed")


def change_purpose(state: State, *, purpose: str) -> Outcome:
    if purpose == state.purpose:
        return Outcome(False, state, "unchanged")
    return Outcome(True, replace(state, purpose=purpose, origin="purpose"), "purpose_changed")


def expire_snapshot(state: State) -> Outcome:
    if not state.has_snapshot:
        return Outcome(False, state, "no_snapshot")
    return Outcome(True, replace(state, expiry=EXPIRED, origin="expire"), "snapshot_expired")


def corrupt_digest(state: State) -> Outcome:
    if not state.has_snapshot:
        return Outcome(False, state, "no_snapshot")
    return Outcome(True, replace(state, digest_valid=False, origin="corrupt"), "digest_corrupted")


def commit(state: State) -> Outcome:
    if not state.has_proposal:
        return Outcome(False, state, "no_proposal")
    return _try_commit(state)


def replay_proposal(state: State) -> Outcome:
    """Re-submit the in-flight proposal.

    If the proposal's idempotency key was already applied this is an idempotent
    replay (no state change, no version advance).  Otherwise admission checks
    are re-run exactly as for a commit.
    """
    if not state.has_proposal:
        return Outcome(False, state, "no_proposal")
    return _try_commit(state)


def retry(state: State) -> Outcome:
    """Re-attempt a previously rejected commit.

    Only valid after a rejection.  Re-runs the full admission predicate, so a
    stale/governance-invalid proposal stays rejected (no unauthorized success).
    """
    if not state.has_proposal:
        return Outcome(False, state, "no_proposal")
    if state.commit_status != COMMIT_REJECTED:
        return Outcome(False, state, "nothing_to_retry")
    return _try_commit(state)


def rollback(state: State) -> Outcome:
    if state.commit_status != COMMIT_APPLIED or state.state_version <= 0:
        return Outcome(False, state, "nothing_to_rollback")
    return Outcome(
        True,
        replace(
            state,
            state_version=state.state_version - 1,
            origin="rollback",
            idempotency_key=None,
            commit_status=COMMIT_ROLLED_BACK,
        ),
        "rolled_back",
    )


def _admission_failure(state: State) -> str | None:
    """Return the first admission failure reason, or ``None`` if admissible."""
    if state.proposal_base is None:
        return "no_proposal"
    if state.proposal_base != state.state_version:
        return "stale_base"
    if state.consent_state != CONSENT_GRANTED:
        return "consent_revoked"
    if state.proposal_consent_version != state.consent_version:
        return "stale_consent_version"
    if state.proposal_actor != state.actor:
        return "actor_mismatch"
    if state.proposal_role != state.role:
        return "role_mismatch"
    if state.proposal_purpose != state.purpose:
        return "purpose_mismatch"
    if state.proposal_task != state.task:
        return "task_mismatch"
    if state.proposal_policy_version != state.policy_version:
        return "stale_policy"
    if state.proposal_binding:
        if not state.has_snapshot:
            return "no_snapshot"
        if not state.digest_valid:
            return "corrupt_digest"
        if state.expiry is None or state.expiry <= EXPIRED:
            return "snapshot_expired"
        if not state.proposal_evidence <= state.disclosed_evidence_set:
            return "evidence_not_disclosed"
    return None


def _try_commit(state: State) -> Outcome:
    key = state.idempotency_key
    if key is not None and key in state.committed_keys:
        # Idempotent replay of an already-applied key: one logical transition,
        # no state change, no version advance.
        return Outcome(True, state, "idempotent_replay", idempotent=True)
    failure = _admission_failure(state)
    if failure is not None:
        return Outcome(False, replace(state, origin="commit", commit_status=COMMIT_REJECTED), failure)
    keys = state.committed_keys | frozenset({key}) if key is not None else state.committed_keys
    nxt = replace(
        state,
        state_version=bump_version(state.state_version),
        snapshot_id=None,
        digest_valid=True,
        expiry=None,
        disclosed_evidence_set=frozenset(),
        proposal_base=None,
        proposal_binding=False,
        proposal_evidence=frozenset(),
        proposal_actor=None,
        proposal_role=None,
        proposal_purpose=None,
        proposal_task=None,
        proposal_policy_version=None,
        proposal_consent_version=None,
        origin="commit",
        idempotency_key=None,
        committed_keys=keys,
        commit_status=COMMIT_APPLIED,
    )
    return Outcome(True, nxt, "committed")


TRANSITION_NAMES = frozenset(
    {
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
)

_HANDLERS = {
    "issue_disclosure": issue_disclosure,
    "create_proposal": create_proposal,
    "advance_state": advance_state,
    "revoke_consent": revoke_consent,
    "change_role": change_role,
    "change_purpose": change_purpose,
    "advance_policy": advance_policy,
    "expire_snapshot": expire_snapshot,
    "corrupt_digest": corrupt_digest,
    "replay_proposal": replay_proposal,
    "commit": commit,
    "retry": retry,
    "rollback": rollback,
}


def apply(state: State, name: str, **params: object) -> Outcome:
    """Dispatch one transition by name."""
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"unknown_transition: {name}")
    return handler(state, **params)
