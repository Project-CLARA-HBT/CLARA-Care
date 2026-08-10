"""Code-owned task/domain sufficiency policy for risk-aware THSS.

These are governance thresholds, not clinical safety claims.  They make the
compiler's abstain/escalate boundary reviewable and versioned rather than
letting a downstream model infer sufficiency from raw health values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class DomainSufficiencyPolicy:
    authority: str
    lifecycle: str
    conflict_policy: str
    temporal_policy: str
    escalation_policy: str
    max_age: timedelta
    min_evidence: int = 1


DOMAIN_POLICIES: dict[str, DomainSufficiencyPolicy] = {
    "medications": DomainSufficiencyPolicy(
        authority="reconciled course or reviewed source",
        lifecycle="active only",
        conflict_policy="open dose/identity conflict blocks task",
        temporal_policy="90-day freshness window",
        escalation_policy="medication reconciliation",
        max_age=timedelta(days=90),
    ),
    "allergies": DomainSufficiencyPolicy(
        authority="patient report or reviewed clinical source",
        lifecycle="active only; entered-in-error is excluded",
        conflict_policy="open reaction/agent conflict blocks task",
        temporal_policy="365-day freshness window",
        escalation_policy="allergy verification",
        max_age=timedelta(days=365),
    ),
    "conditions": DomainSufficiencyPolicy(
        authority="problem-list or reviewed clinical source",
        lifecycle="active only",
        conflict_policy="open status/diagnosis conflict blocks task",
        temporal_policy="180-day freshness window",
        escalation_policy="problem-list review",
        max_age=timedelta(days=180),
    ),
    "observations": DomainSufficiencyPolicy(
        authority="identified laboratory or chronic-state source",
        lifecycle="active only",
        conflict_policy="open value/unit conflict blocks task",
        temporal_policy="30-day freshness window",
        escalation_policy="repeat measurement or clinician review",
        max_age=timedelta(days=30),
    ),
}


TASK_CRITICAL_CLASSES: dict[str, frozenset[str]] = {
    "drugbank_ddi": frozenset({"medications"}),
    "careguard": frozenset({"medications", "allergies"}),
    "careguard_reconciliation": frozenset({"medications", "allergies"}),
    "chronic_state_review": frozenset({"conditions", "observations"}),
}


def critical_classes_for_task(task: str) -> frozenset[str]:
    return TASK_CRITICAL_CLASSES.get(task, frozenset())
