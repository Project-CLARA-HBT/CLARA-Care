"""Pure projection of reconciled commitment product state to THSS fields (P10).

P10 - Harmonized abstention vocabulary
--------------------------------------
Both THSS compilers (generic ``gateway.compile_thss`` and
``commitment_thss.compile_commitment_thss``) must speak one abstention
vocabulary.  ``AbstentionDecision`` is that shared enum:

* ``ABSTAIN_ESCALATE`` / ``USABLE`` - the sufficiency decision codes used by
  ``sufficiency["decision"]`` (commitment THSS) and ``risk["decision"]``
  (generic THSS ``selection_policy="risk_aware"``).
* ``INSUFFICIENT_EVIDENCE`` / ``CONFLICTED`` - the evidence-state codes that
  drive abstention; they also appear as per-commitment ``evidence_state`` and
  as generic escalation reason codes.

Mapping (values are byte-identical strings in both compilers):

    generic risk.decision  "ABSTAIN_ESCALATE"  == commitment sufficiency.decision
    generic risk.decision  "USABLE"            == commitment sufficiency.decision
    evidence_state         "CONFLICTED"        -> abstention_reason "CONFLICTED"
    evidence_state         "INSUFFICIENT_EVIDENCE" -> abstention_reason
                                                      "INSUFFICIENT_EVIDENCE"

P12 - Canonical vs derived state
--------------------------------
``project_commitment`` is a read-only pure function over visible evidence.  It
never writes canonical health state (``GlhsStateVersion`` /
``GlhsClinicalCommitmentVersion``); the ONLY write path is
``commitment_gateway.apply_commitment_transition``.  Projection functions
raise ``RuntimeError`` when a session/write API is passed and never mutate
their input.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any


class AbstentionDecision(StrEnum):
    """Shared sufficiency/abstention code vocabulary for THSS compilers."""

    ABSTAIN_ESCALATE = "ABSTAIN_ESCALATE"
    USABLE = "USABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTED = "CONFLICTED"


ABSTENTION_CODES = frozenset(item.value for item in AbstentionDecision)


def sufficiency_decision(*, must_abstain: bool) -> str:
    """Map a compiler's abstain flag to the shared decision code."""

    return (
        AbstentionDecision.ABSTAIN_ESCALATE.value
        if must_abstain
        else AbstentionDecision.USABLE.value
    )


def _guard_pure_input(value: Any) -> None:
    if isinstance(value, Mapping):
        if any(name in value for name in ("session", "write_api")):
            raise RuntimeError("commitment projection is read-only: write API rejected")
        return
    if hasattr(value, "add") and hasattr(value, "flush") and hasattr(value, "commit"):
        raise RuntimeError("commitment projection is read-only: session/write API rejected")
    raise RuntimeError("commitment projection accepts mapping input only")


def project_commitment(
    commitment_state: Mapping[str, Any], *, strict: bool = True
) -> dict[str, Any]:
    """Project one reconciled commitment product state to THSS-visible fields.

    ``commitment_state`` is the derived (never canonical) commitment-visible
    dict produced by the reconciliation/selection pipeline (e.g. items from
    ``commitment_gateway.reconstruct_commitments`` plus matched evidence).
    ``strict`` mirrors the commitment THSS ``strict`` flag: abstention is only
    *recommended* (never forced) under strict selection.
    """

    _guard_pure_input(commitment_state)
    commitment_id = str(commitment_state["commitment_id"])
    evidence_state = str(commitment_state.get("evidence_state") or "INSUFFICIENT_EVIDENCE")
    lifecycle = str(commitment_state.get("lifecycle_state") or "OPEN")
    timeliness = str(commitment_state.get("timeliness_state") or "UNKNOWN")
    reason_codes = [str(item) for item in (commitment_state.get("reason_codes") or ())]
    decisive_valid_time = commitment_state.get("decisive_valid_time") or commitment_state.get(
        "anchor_valid_time"
    )
    matched_evidence_ids = [
        str(item)
        for item in (
            commitment_state.get("evidence_ids")
            or commitment_state.get("matched_evidence_ids")
            or ()
        )
    ]
    escalation: list[dict[str, Any]] = []
    abstention_reason: str | None = None
    if evidence_state == AbstentionDecision.CONFLICTED.value:
        escalation.append({"code": "commitment_conflict", "commitment_id": commitment_id})
        abstention_reason = AbstentionDecision.CONFLICTED.value
    elif evidence_state == AbstentionDecision.INSUFFICIENT_EVIDENCE.value:
        escalation.append(
            {"code": "commitment_insufficient_evidence", "commitment_id": commitment_id}
        )
        abstention_reason = AbstentionDecision.INSUFFICIENT_EVIDENCE.value
    abstention_recommended = strict and abstention_reason is not None
    return {
        "commitment_id": commitment_id,
        "lifecycle": lifecycle,
        "evidence_state": evidence_state,
        "timeliness": timeliness,
        "reason_codes": reason_codes,
        "decisive_valid_time": decisive_valid_time,
        "matched_evidence_ids": matched_evidence_ids,
        "escalation": escalation,
        "abstention_recommended": abstention_recommended,
        "abstention_reason": abstention_reason,
        # Derived per-commitment decision code from the shared vocabulary.
        "abstention_decision": sufficiency_decision(must_abstain=abstention_recommended),
    }
