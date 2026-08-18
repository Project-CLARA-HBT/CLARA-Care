"""Deterministic bitemporal reconciliation for Clinical Commitments.

Legacy compatibility surface: ``evaluate_commitment`` and the six-field
``CommitmentProductState`` remain importable and behavior-compatible.  The
actual reconciliation logic now lives in the P1 engine
``clara_api.glhs.commitment_reconciliation.reconcile_commitment``; this module
delegates to it and projects the six compatibility fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from clara_api.glhs.commitment_reconciliation import reconcile_commitment


@dataclass(frozen=True)
class CommitmentProductState:
    lifecycle_state: str
    evidence_state: str
    timeliness_state: str
    matched_evidence_ids: tuple[str, ...]
    excluded_evidence: tuple[dict[str, str], ...]
    reason_codes: tuple[str, ...]


def evaluate_commitment(
    version: object,
    events: list[dict],
    *,
    valid_at: datetime,
    known_at: datetime,
) -> CommitmentProductState:
    """Evaluate a frozen version without mutating canonical state.

    Delegates to the P1 Commitment Reconciliation Engine; the returned product
    state preserves the historical six-field shape and reason-code vocabulary.
    """

    state = reconcile_commitment(
        version, events, valid_at=valid_at, known_at=known_at
    )
    return CommitmentProductState(
        lifecycle_state=state.lifecycle_state,
        evidence_state=state.evidence_state,
        timeliness_state=state.timeliness_state,
        matched_evidence_ids=state.matched_evidence_ids,
        excluded_evidence=state.excluded_evidence,
        reason_codes=state.reason_codes,
    )
