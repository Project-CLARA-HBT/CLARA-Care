"""Incremental admissibility clauses for disclosure-to-write isolation."""

from __future__ import annotations

from dataclasses import dataclass

VARIANTS = (
    "temporal_provenance_resolver",
    "base_version_write",
    "authorization_at_disclosure",
    "provenance_audit",
    "snapshot_id_binding",
    "snapshot_context_binding",
    "complete_glhs_contract",
)


@dataclass(frozen=True)
class ContractCase:
    case_id: str
    profile_matches: bool = True
    base_version_matches: bool = True
    authorized_at_disclosure: bool = True
    provenance_present: bool = True
    snapshot_id_matches: bool = True
    actor_matches: bool = True
    actor_role_matches: bool = True
    purpose_matches: bool = True
    task_matches: bool = True
    digest_matches: bool = True
    evidence_within_snapshot: bool = True
    snapshot_unexpired: bool = True
    authorized_at_write: bool = True
    policy_matches: bool = True
    consent_matches: bool = True


@dataclass(frozen=True)
class ClauseOutcome:
    accepted: bool
    reason_code: str
    exact_seen_context_reconstructable: bool
    audit_link_present: bool


def evaluate(variant: str, case: ContractCase) -> ClauseOutcome:
    if variant not in VARIANTS:
        raise ValueError("unknown_contract_variant")
    clauses = VARIANTS[: VARIANTS.index(variant) + 1]
    reason = "accepted"
    if "base_version_write" in clauses:
        if not case.profile_matches:
            reason = "profile_mismatch"
        elif not case.base_version_matches:
            reason = "base_version_mismatch"
    if (
        reason == "accepted"
        and "authorization_at_disclosure" in clauses
        and not case.authorized_at_disclosure
    ):
        reason = "authorization_at_disclosure_denied"
    if reason == "accepted" and "provenance_audit" in clauses and not case.provenance_present:
        reason = "provenance_required"
    if (
        reason == "accepted"
        and "snapshot_id_binding" in clauses
        and not case.snapshot_id_matches
    ):
        reason = "snapshot_id_mismatch"
    if reason == "accepted" and "snapshot_context_binding" in clauses:
        for matches, mismatch_reason in (
            (case.actor_matches, "actor_mismatch"),
            (case.actor_role_matches, "actor_role_mismatch"),
            (case.purpose_matches, "purpose_mismatch"),
            (case.task_matches, "task_mismatch"),
            (case.digest_matches, "snapshot_digest_mismatch"),
            (case.evidence_within_snapshot, "evidence_not_disclosed"),
        ):
            if not matches:
                reason = mismatch_reason
                break
    if reason == "accepted" and "complete_glhs_contract" in clauses:
        for matches, mismatch_reason in (
            (case.snapshot_unexpired, "snapshot_expired"),
            (case.authorized_at_write, "current_reauthorization_denied"),
            (case.policy_matches, "policy_version_mismatch"),
            (case.consent_matches, "consent_version_mismatch"),
        ):
            if not matches:
                reason = mismatch_reason
                break
    accepted = reason == "accepted"
    return ClauseOutcome(
        accepted=accepted,
        reason_code=reason,
        exact_seen_context_reconstructable=(
            "snapshot_context_binding" in clauses
            and case.snapshot_id_matches
            and case.actor_matches
            and case.actor_role_matches
            and case.purpose_matches
            and case.task_matches
            and case.digest_matches
            and case.evidence_within_snapshot
        ),
        audit_link_present="provenance_audit" in clauses,
    )
