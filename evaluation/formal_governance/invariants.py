"""Machine-checkable invariants over canonical states and transitions.

Each function returns a list of violated invariant ids; an empty list means the
invariant family holds.  The enumerator checks these *independently* of the
transition admission logic, so a deliberately weakened (mutated) model surfaces
as a recorded counterexample instead of being silently accepted.

The eleven required invariants:

  I1  no bound proposal commits with stale base state
  I2  no post-revocation commit
  I3  no wrong actor/role/purpose/task commit
  I4  no expired/tampered snapshot commit
  I5  no evidence outside the disclosed subset supports a bound commit
  I6  idempotent replay yields one logical transition
  I7  successful commit advances the version exactly once
  I8  rejected transition does not advance canonical state
  I9  admitted transition is reconstructable (deterministic)
  I10 current policy coordinate participates in admission
  I11 a clean valid proposal can commit in an admissible state

I1-I10 are checked per transition (and/or per state where expressible).  I11 is
a positive reachability property checked on the initial state.
"""

from __future__ import annotations

from dataclasses import replace

from .model import (
    COMMIT_APPLIED,
    COMMIT_STATUSES,
    CONSENT_GRANTED,
    CONSENT_STATES,
    EVIDENCE_UNIVERSE,
    EXPIRED,
    MAX_VERSION,
    ORIGINS,
    TTL,
    State,
    bump_version,
)
from .transitions import Outcome, apply

# Transitions that attempt to write committed state.
COMMIT_TRANSITIONS = frozenset({"commit", "replay_proposal", "retry"})


def state_invariants(state: State) -> list[str]:
    """State-predicate invariants that must hold for every reached state."""
    violated: list[str] = []
    if state.consent_state not in CONSENT_STATES:
        violated.append("vocab_consent_state")
    if state.commit_status not in COMMIT_STATUSES:
        violated.append("vocab_commit_status")
    if state.origin not in ORIGINS:
        violated.append("vocab_origin")
    if not 0 <= state.state_version <= MAX_VERSION:
        violated.append("version_state_in_domain")
    if not 0 <= state.policy_version <= MAX_VERSION:
        violated.append("version_policy_in_domain")
    if not 0 <= state.consent_version <= MAX_VERSION:
        violated.append("version_consent_in_domain")
    if state.expiry is not None and state.expiry not in (EXPIRED, TTL):
        violated.append("expiry_in_domain")
    if not state.has_snapshot and not state.digest_valid:
        violated.append("digest_consistent")
    if state.commit_status == COMMIT_APPLIED and state.has_proposal:
        violated.append("commit_applied_consumes_proposal")
    if state.commit_status == COMMIT_APPLIED and state.has_snapshot:
        violated.append("commit_applied_consumes_snapshot")
    if state.proposal_binding and not state.has_proposal:
        violated.append("bound_implies_proposal")
    if state.proposal_binding and state.proposal_policy_version is None:
        violated.append("bound_records_policy")
    if not state.proposal_evidence <= EVIDENCE_UNIVERSE:
        violated.append("evidence_in_universe")
    if not state.disclosed_evidence_set <= EVIDENCE_UNIVERSE:
        violated.append("disclosed_in_universe")
    return violated


def transition_invariants(
    source: State, name: str, params: dict[str, object], outcome: Outcome
) -> list[str]:
    """Transition invariants over one attempted transition."""
    violated: list[str] = []
    if not outcome.admitted:
        if outcome.state.canonical != source.canonical:
            violated.append("I8_rejected_does_not_advance")
        return violated

    if outcome.idempotent:
        if outcome.state != source:
            violated.append("I6_idempotent_replay_one_transition")
        if outcome.state.state_version != source.state_version:
            violated.append("I6_idempotent_replay_one_transition")
        return violated

    is_commit_attempt = name in COMMIT_TRANSITIONS
    is_success = outcome.reason == "committed" and not outcome.idempotent

    if is_commit_attempt and is_success:
        if source.proposal_base is None or source.proposal_base != source.state_version:
            violated.append("I1_no_stale_base_commit")
        if source.consent_state != CONSENT_GRANTED:
            violated.append("I2_no_post_revocation_commit")
        if source.proposal_consent_version != source.consent_version:
            violated.append("I2_no_post_revocation_commit")
        for field_name in ("actor", "role", "purpose", "task"):
            if getattr(source, f"proposal_{field_name}") != getattr(source, field_name):
                violated.append("I3_no_wrong_coordinate_commit")
        if source.proposal_binding:
            if not source.has_snapshot or not source.digest_valid:
                violated.append("I4_no_expired_tampered_snapshot_commit")
            if source.expiry is None or source.expiry <= EXPIRED:
                violated.append("I4_no_expired_tampered_snapshot_commit")
            if not source.proposal_evidence <= source.disclosed_evidence_set:
                violated.append("I5_no_undisclosed_evidence")
        if source.proposal_policy_version != source.policy_version:
            violated.append("I10_current_policy_in_admission")
        if outcome.state.state_version != bump_version(source.state_version):
            violated.append("I7_commit_advances_once")

    # I9: an admitted transition is reconstructable — re-applying the same
    # transition to the source reproduces the identical outcome.
    if apply(source, name, **params) != outcome:
        violated.append("I9_admitted_reconstructable")
    return violated


def check_i11(initial: State) -> bool:
    """I11: a clean valid proposal can commit in an admissible state."""
    disclosure = apply(initial, "issue_disclosure", evidence=frozenset({"e0"}), expiry=TTL)
    if not disclosure.admitted:
        return False
    proposal = apply(
        disclosure.state,
        "create_proposal",
        binding=True,
        evidence=frozenset({"e0"}),
        idempotency_key="k0",
    )
    if not proposal.admitted:
        return False
    outcome = apply(proposal.state, "commit")
    return (
        outcome.admitted
        and not outcome.idempotent
        and outcome.reason == "committed"
        and outcome.state.commit_status == COMMIT_APPLIED
        and outcome.state.state_version == bump_version(initial.state_version)
    )


def all_invariant_ids() -> list[str]:
    """All machine-checkable invariant ids for report/tests."""
    return [
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


def build_state(initial: State, **overrides: object) -> State:
    """Shorthand for constructing adversarial test states."""
    return replace(initial, **overrides)


def synthetic_success(source: State, target: State) -> Outcome:
    """A synthetic admitted commit outcome used to test the I1-I10 checkers."""
    return Outcome(True, target, "committed")
