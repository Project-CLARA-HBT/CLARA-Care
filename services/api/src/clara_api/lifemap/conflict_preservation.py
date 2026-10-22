"""Clinical Uncertainty and Conflict Preservation Engine.

Spec: PH10 / A03 (Domain + GLHS Services).
Enforces:
1. Multi-source conflict preservation: conflicting doctor diagnoses or patient disputes are retained as parallel assertions rather than overwritten.
2. Explicit clinical uncertainty modeling (confidence intervals, epistemic ambiguity).
3. Patient dispute tracking with non-destructive audit linkage.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any, Literal

AssertionStatus = Literal["CONFIRMED", "DISPUTED", "UNCERTAIN", "SUPERSEDED"]


@dataclasses.dataclass(frozen=True)
class PreservedClinicalAssertion:
    assertion_id: str
    event_id: str
    claim_text: str
    source_author: str
    status: AssertionStatus
    confidence: float
    dispute_notes: str | None
    recorded_at: datetime.datetime


class ConflictPreservationEngine:
    """Manages parallel competing clinical assertions without destructive overwrites."""

    def __init__(self) -> None:
        self._assertions: dict[str, list[PreservedClinicalAssertion]] = {}

    def record_assertion(
        self,
        *,
        event_id: str,
        assertion_id: str,
        claim_text: str,
        source_author: str,
        status: AssertionStatus = "CONFIRMED",
        confidence: float = 1.0,
        dispute_notes: str | None = None,
    ) -> PreservedClinicalAssertion:
        assertion = PreservedClinicalAssertion(
            assertion_id=assertion_id,
            event_id=event_id,
            claim_text=claim_text,
            source_author=source_author,
            status=status,
            confidence=confidence,
            dispute_notes=dispute_notes,
            recorded_at=datetime.datetime.now(datetime.UTC),
        )
        self._assertions.setdefault(event_id, []).append(assertion)
        return assertion

    def dispute_assertion(
        self,
        *,
        event_id: str,
        assertion_id: str,
        disputing_actor: str,
        dispute_reason: str,
    ) -> PreservedClinicalAssertion | None:
        """Records a dispute against an existing assertion without deleting the original."""
        chain = self._assertions.get(event_id, [])
        target = next((a for a in chain if a.assertion_id == assertion_id), None)
        if not target:
            return None

        dispute_entry = self.record_assertion(
            event_id=event_id,
            assertion_id=f"disp-{assertion_id}",
            claim_text=f"Dispute against: {target.claim_text}",
            source_author=disputing_actor,
            status="DISPUTED",
            confidence=0.5,
            dispute_notes=dispute_reason,
        )
        return dispute_entry

    def get_competing_assertions(self, event_id: str) -> list[PreservedClinicalAssertion]:
        """Returns all historical and competing assertions for a clinical event."""
        return self._assertions.get(event_id, [])
