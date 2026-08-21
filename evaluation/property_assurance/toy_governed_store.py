"""Independent minimal governed-store contract used for SOICT external-validity checks.

This module intentionally imports no CLARA/GLHS production code. It models only
the co-versioned disclosure-to-commit coordinates required by the assurance
protocol, and is not a clinical store or a second implementation of CLARA.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256


class ToyGovernanceError(ValueError):
    """Raised when a proposal no longer matches current governed state."""


@dataclass(frozen=True)
class ToySnapshot:
    subject: str
    actor: str
    purpose: str
    state_version: int
    policy_version: int
    consent_version: int
    expires_at: datetime
    digest: str


@dataclass(frozen=True)
class ToyProposal:
    proposal_id: str
    snapshot: ToySnapshot


class ToyGovernedStore:
    """Small independent reference contract for sequence-sensitive invariants."""

    def __init__(self, *, subject: str, actor: str, purpose: str) -> None:
        self.subject = subject
        self.actor = actor
        self.purpose = purpose
        self.state_version = 0
        self.policy_version = 0
        self.consent_version = 0
        self.committed: dict[str, int] = {}

    def issue_snapshot(self, *, now: datetime) -> ToySnapshot:
        expires_at = now.astimezone(UTC) + timedelta(minutes=5)
        coordinates = self._coordinates(expires_at=expires_at)
        return ToySnapshot(**coordinates, digest=_digest(coordinates))

    def propose(self, *, proposal_id: str, snapshot: ToySnapshot) -> ToyProposal:
        if not proposal_id:
            raise ToyGovernanceError("proposal_id_required")
        return ToyProposal(proposal_id=proposal_id, snapshot=snapshot)

    def commit(self, *, proposal: ToyProposal, now: datetime) -> int:
        if proposal.proposal_id in self.committed:
            return self.committed[proposal.proposal_id]
        snapshot = proposal.snapshot
        if snapshot.expires_at <= now.astimezone(UTC):
            raise ToyGovernanceError("snapshot_expired")
        snapshot_coordinates = {
            "subject": snapshot.subject,
            "actor": snapshot.actor,
            "purpose": snapshot.purpose,
            "state_version": snapshot.state_version,
            "policy_version": snapshot.policy_version,
            "consent_version": snapshot.consent_version,
            "expires_at": snapshot.expires_at,
        }
        if _digest(snapshot_coordinates) != snapshot.digest:
            raise ToyGovernanceError("snapshot_digest_mismatch")
        coordinates = self._coordinates(expires_at=snapshot.expires_at)
        for name in (
            "subject",
            "actor",
            "purpose",
            "state_version",
            "policy_version",
            "consent_version",
        ):
            if getattr(snapshot, name) != coordinates[name]:
                raise ToyGovernanceError(f"snapshot_{name}_mismatch")
        self.state_version += 1
        self.committed[proposal.proposal_id] = self.state_version
        return self.state_version

    def change_state(self) -> None:
        self.state_version += 1

    def change_policy(self) -> None:
        self.policy_version += 1

    def change_consent(self) -> None:
        self.consent_version += 1

    def change_actor(self, actor: str) -> None:
        self.actor = actor

    def change_purpose(self, purpose: str) -> None:
        self.purpose = purpose

    def _coordinates(self, *, expires_at: datetime) -> dict[str, object]:
        return {
            "subject": self.subject,
            "actor": self.actor,
            "purpose": self.purpose,
            "state_version": self.state_version,
            "policy_version": self.policy_version,
            "consent_version": self.consent_version,
            "expires_at": expires_at,
        }


def _digest(value: object) -> str:
    return sha256(repr(value).encode("utf-8")).hexdigest()
