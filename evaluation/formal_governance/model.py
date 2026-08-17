"""Compact canonical state model for the formal governance assurance workstream.

This module is deliberately CLARA/GLHS-agnostic.  It models only the finite
coordinates a governed commit depends on: *who* (subject/actor/role), *for what*
(purpose/task), *against which versions* (state/policy/consent), *under which
authorization artifacts* (disclosure snapshot, disclosed evidence, proposal
binding) and *with what outcome* (idempotency key, commit status, provenance).

Coordinate domains are kept small and finite so the bounded exhaustive
enumerator in ``explore.py`` sweeps the whole reachable space in seconds.
Version coordinates saturate at ``MAX_VERSION``; expiry uses the ``EXPIRED``
sentinel; evidence comes from the two-item ``EVIDENCE_UNIVERSE``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

CONSENT_GRANTED = "granted"
CONSENT_REVOKED = "revoked"
CONSENT_STATES = frozenset({CONSENT_GRANTED, CONSENT_REVOKED})

COMMIT_NONE = "none"
COMMIT_APPLIED = "applied"
COMMIT_REJECTED = "rejected"
COMMIT_ROLLED_BACK = "rolled_back"
COMMIT_STATUSES = frozenset({COMMIT_NONE, COMMIT_APPLIED, COMMIT_REJECTED, COMMIT_ROLLED_BACK})

ORIGIN_INITIAL = "initial"
ORIGINS = frozenset(
    {
        ORIGIN_INITIAL,
        "disclosure",
        "proposal",
        "state",
        "consent",
        "role",
        "purpose",
        "policy",
        "expire",
        "corrupt",
        "commit",
        "rollback",
    }
)

# Expiry is an absolute deadline.  ``EXPIRED`` is the sentinel written by the
# ``expire_snapshot`` transition; a disclosure issued with ``TTL`` is alive.
EXPIRED = 0
TTL = 1

# Version coordinates saturate at this bound so the reachable state space is
# finite.  Invariant checks depend on *equality* between coordinates, which
# saturation preserves: a proposal recorded at the capped version still matches
# the capped current version, so no invariant is lost.  A domain of {0, 1} is
# already enough to exercise stale-version rejection for every coordinate.
MAX_VERSION = 1

# Small finite evidence universe used by the enumerator.  Disclosed evidence
# and proposal evidence are always subsets of this universe.
EVIDENCE_UNIVERSE = frozenset({"e0", "e1"})


def bump_version(version: int) -> int:
    """Advance a version coordinate by one, saturating at ``MAX_VERSION``."""
    return min(version + 1, MAX_VERSION)


@dataclass(frozen=True)
class State:
    """One canonical governance state."""

    subject: str
    actor: str
    role: str
    purpose: str
    task: str
    state_version: int
    policy_version: int
    consent_version: int
    consent_state: str
    snapshot_id: str | None
    digest_valid: bool
    expiry: int | None
    disclosed_evidence_set: frozenset[str]
    proposal_base: int | None
    proposal_binding: bool
    proposal_evidence: frozenset[str]
    proposal_actor: str | None
    proposal_role: str | None
    proposal_purpose: str | None
    proposal_task: str | None
    proposal_policy_version: int | None
    proposal_consent_version: int | None
    # Provenance is not part of governance identity: two states that differ only
    # in how they were reached are the same canonical state.
    origin: str = field(compare=False)
    idempotency_key: str | None = None
    committed_keys: frozenset[str] = frozenset()
    commit_status: str = COMMIT_NONE

    @property
    def canonical(self) -> tuple[object, ...]:
        """The coordinate tuple a rejected transition must never change."""
        return (
            self.subject,
            self.actor,
            self.role,
            self.purpose,
            self.task,
            self.state_version,
            self.policy_version,
            self.consent_version,
            self.consent_state,
        )

    @property
    def has_proposal(self) -> bool:
        return self.proposal_base is not None

    @property
    def has_snapshot(self) -> bool:
        return self.snapshot_id is not None

    @property
    def snapshot_alive(self) -> bool:
        """A snapshot is alive iff it exists, is digest-valid and unexpired."""
        return (
            self.has_snapshot
            and self.digest_valid
            and self.expiry is not None
            and self.expiry > EXPIRED
        )


def initial_state(
    *,
    subject: str = "s0",
    actor: str = "a0",
    role: str = "r0",
    purpose: str = "p0",
    task: str = "t0",
) -> State:
    """A fresh, fully-admissible governance state."""
    return State(
        subject=subject,
        actor=actor,
        role=role,
        purpose=purpose,
        task=task,
        state_version=0,
        policy_version=0,
        consent_version=0,
        consent_state=CONSENT_GRANTED,
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
        origin=ORIGIN_INITIAL,
        idempotency_key=None,
        committed_keys=frozenset(),
        commit_status=COMMIT_NONE,
    )


def snapshot_digest(state: State, *, evidence: frozenset[str], expiry: int) -> str:
    """Deterministic disclosure id bound to the current canonical coordinates."""
    payload = (
        state.subject,
        state.actor,
        state.role,
        state.purpose,
        state.task,
        state.state_version,
        state.policy_version,
        state.consent_version,
        tuple(sorted(evidence)),
        expiry,
    )
    return sha256(repr(payload).encode("utf-8")).hexdigest()
