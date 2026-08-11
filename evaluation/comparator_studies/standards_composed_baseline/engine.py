"""Temporal/provenance state plus version-aware authorized write semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from evaluation.comparator_studies.bitemporal_state_arbitration.engine import (
    ArbitrationEvent,
    ArbitrationResult,
    arbitrate,
)


@dataclass(frozen=True)
class MechanismProposal:
    proposal_id: str
    profile_id: str
    actor_id: str
    purpose: str
    observed_base_version: int
    provenance_ids: tuple[str, ...]
    resource_key: str
    value: object
    source_snapshot_id: str | None = None
    source_snapshot_digest: str | None = None


@dataclass(frozen=True)
class MechanismDecision:
    accepted: bool
    reason_code: str
    base_version: int
    resulting_version: int
    audit_index: int


@dataclass
class StandardsComposedState:
    """Semantic baseline, explicitly not a faithful FHIR product/server."""

    profile_id: str
    state_version: int = 0
    authorization: set[tuple[str, str]] = field(default_factory=set)
    resources: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, tuple[str, ...]] = field(default_factory=dict)
    audit: list[dict[str, object]] = field(default_factory=list)

    def authorize(self, *, actor_id: str, purpose: str) -> None:
        self.authorization.add((actor_id, purpose))

    def revoke(self, *, actor_id: str, purpose: str) -> None:
        self.authorization.discard((actor_id, purpose))

    def resolve(
        self,
        events: list[ArbitrationEvent],
        *,
        valid_at: datetime,
        known_at: datetime,
    ) -> ArbitrationResult:
        """Apply the existing bitemporal/provenance mechanism at explicit cutoffs."""

        return arbitrate(events, valid_at=valid_at, known_at=known_at)

    def apply(self, proposal: MechanismProposal) -> MechanismDecision:
        """Apply current authorization plus an If-Match-style version check.

        Snapshot fields are retained in the audit record but intentionally do
        not affect admissibility. That omission is the isolated difference from
        exact disclosure-context binding, not an accidental weak baseline.
        """

        reason = "accepted"
        if proposal.profile_id != self.profile_id:
            reason = "profile_mismatch"
        elif (proposal.actor_id, proposal.purpose) not in self.authorization:
            reason = "current_authorization_denied"
        elif proposal.observed_base_version != self.state_version:
            reason = "if_match_version_mismatch"
        elif not proposal.provenance_ids:
            reason = "provenance_required"
        accepted = reason == "accepted"
        base = self.state_version
        if accepted:
            self.resources[proposal.resource_key] = proposal.value
            self.provenance[proposal.resource_key] = proposal.provenance_ids
            self.state_version += 1
        self.audit.append(
            {
                "proposal_id": proposal.proposal_id,
                "profile_id": proposal.profile_id,
                "actor_id": proposal.actor_id,
                "purpose": proposal.purpose,
                "observed_base_version": proposal.observed_base_version,
                "source_snapshot_id": proposal.source_snapshot_id,
                "source_snapshot_digest": proposal.source_snapshot_digest,
                "provenance_ids": list(proposal.provenance_ids),
                "accepted": accepted,
                "reason_code": reason,
                "base_version": base,
                "resulting_version": self.state_version,
            }
        )
        return MechanismDecision(
            accepted=accepted,
            reason_code=reason,
            base_version=base,
            resulting_version=self.state_version,
            audit_index=len(self.audit) - 1,
        )
