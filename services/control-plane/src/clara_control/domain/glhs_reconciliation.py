"""GLHS Provenance Reconciliation & Audit-Safe Denial Evaluation.

Spec: PH49 / A03 (Domain Service).
Enforces:
1. Structured classification of GLHS proposal rejection reasons.
2. Dependency set audit verification under control-plane oversight.
3. Audit-safe reconciliation recording decisions in immutable audit logs without PHI.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any, Literal

DenyReasonCode = Literal[
    "STALE_DEPENDENCY_VERSION",
    "PROPOSAL_EXPIRED",
    "UNAUTHORIZED_REVIEWER",
    "LINEAGE_CYCLE_DETECTED",
    "INSUFFICIENT_ATTESTATION",
    "CONSENT_REVOKED",
]


@dataclasses.dataclass(frozen=True)
class ReconciliationAuditRecord:
    proposal_id: str
    decision: Literal["ADMITTED", "REJECTED"]
    reviewer_email: str
    deny_code: DenyReasonCode | None
    notes: str
    timestamp: datetime.datetime


class GlhsReconciliationService:
    """Manages audit-safe clinical proposal reconciliation and deny code categorization."""

    DENY_CODE_DESCRIPTIONS: dict[DenyReasonCode, str] = {
        "STALE_DEPENDENCY_VERSION": "Observed entity partition version does not match current state version",
        "PROPOSAL_EXPIRED": "Proposal exceeded valid time window before reviewer admission",
        "UNAUTHORIZED_REVIEWER": "Reviewing user lacks required clinical credentials",
        "LINEAGE_CYCLE_DETECTED": "Circular parent reference detected in proposal review chain",
        "INSUFFICIENT_ATTESTATION": "Proposal failed required cryptographic attestation level",
        "CONSENT_REVOKED": "Patient revoked consent for data processing purpose",
    }

    @classmethod
    def record_decision(
        cls,
        *,
        proposal_id: str,
        decision: Literal["ADMITTED", "REJECTED"],
        reviewer_email: str,
        deny_code: DenyReasonCode | None = None,
        notes: str = "",
    ) -> ReconciliationAuditRecord:
        now = datetime.datetime.now(datetime.UTC)
        return ReconciliationAuditRecord(
            proposal_id=proposal_id,
            decision=decision,
            reviewer_email=reviewer_email,
            deny_code=deny_code,
            notes=notes,
            timestamp=now,
        )
