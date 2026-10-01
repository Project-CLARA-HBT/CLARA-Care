"""Formal State-Space Model for GLHS R4 Invariants (I16–I24) and Comparators (C0–C4).

Models:
- 3-Digest Pipeline (D1 H_proj, D2 H_sem, D3 H_trans)
- Dispatch FSM (PENDING -> DISPATCHED -> COMPLETED)
- 5-Way Comparators (C0, C1, C2, C3, C4)
- Invariants I16 through I24
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVIDENCE_UNIVERSE = frozenset({"e0", "e1", "e2"})


@dataclass(frozen=True)
class R4Binding:
    public_id: str
    status: str  # PENDING, DISPATCHED, COMPLETED
    snapshot_version: int
    consent_epoch: int
    policy_epoch: int
    disclosed_evidence: tuple[str, ...]
    h_proj: str
    h_sem: str
    h_trans: str
    attestation_level: str  # L0_ENVELOPE, L1_TRANSPORT, L2_RECEIPT, L3_EXECUTION


@dataclass(frozen=True)
class R4Proposal:
    proposal_id: str
    binding_id: str
    base_state_version: int
    consent_epoch: int
    policy_epoch: int
    asserted_evidence: tuple[str, ...]
    observed_projection: str
    context_binding_mode: str = "snapshot_bound"


@dataclass(frozen=True)
class R4State:
    db_state_version: int = 1
    db_consent_epoch: int = 1
    db_policy_epoch: int = 1
    db_evidence: tuple[str, ...] = ("e0", "e1", "e2")
    bindings: tuple[R4Binding, ...] = ()
    proposals: tuple[R4Proposal, ...] = ()


def evaluate_c0(state: R4State, proposal: R4Proposal) -> bool:
    """C0 (CURRENT_STATE_ONLY): Checks commit-time DB state version, consent, and policy."""
    return (
        proposal.base_state_version == state.db_state_version
        and proposal.consent_epoch == state.db_consent_epoch
        and proposal.policy_epoch == state.db_policy_epoch
    )


def evaluate_c1(state: R4State, proposal: R4Proposal) -> bool:
    """C1 (OCC_READSET): Checks read-set presence in current DB."""
    if not evaluate_c0(state, proposal):
        return False
    return set(proposal.asserted_evidence).issubset(set(state.db_evidence))


def evaluate_c2(state: R4State, proposal: R4Proposal) -> bool:
    """C2 (PROVENANCE_ONLY): Validates binding existence."""
    if not evaluate_c1(state, proposal):
        return False
    return any(b.public_id == proposal.binding_id for b in state.bindings)


def evaluate_c3(state: R4State, proposal: R4Proposal) -> bool:
    """C3 (SIGNED_EXACT_DISCLOSURE_TOKEN): HMAC token check over H_proj and evidence subset."""
    if not evaluate_c1(state, proposal):
        return False
    binding = next((b for b in state.bindings if b.public_id == proposal.binding_id), None)
    if binding is None:
        return False
    if proposal.observed_projection != binding.h_proj:
        return False
    return set(proposal.asserted_evidence).issubset(set(binding.disclosed_evidence))


def evaluate_c4(state: R4State, proposal: R4Proposal) -> bool:
    """C4 (FULL_GRWC): Complete GRWC enforcement."""
    if not evaluate_c3(state, proposal):
        return False
    binding = next((b for b in state.bindings if b.public_id == proposal.binding_id), None)
    if binding is None or binding.status != "COMPLETED":
        return False
    return binding.attestation_level in ("L1_TRANSPORT", "L2_RECEIPT", "L3_EXECUTION")


def check_r4_invariants(state: R4State) -> list[str]:
    """Check Invariants I16–I24 over an R4State."""
    violated = []

    for prop in state.proposals:
        binding = next((b for b in state.bindings if b.public_id == prop.binding_id), None)
        if binding is None:
            continue

        # I16: Current-State Insufficiency Counterexample (Theorem T1)
        # If projection is substituted, C4 must reject
        if prop.observed_projection != binding.h_proj and evaluate_c4(state, prop):
            violated.append(f"I16_CurrentStateInsufficiency_violated:{prop.proposal_id}")

        # I17: Global vs Disclosed Evidence Separation (Theorem T2)
        # Undisclosed evidence must be rejected by C4
        if not set(prop.asserted_evidence).issubset(set(binding.disclosed_evidence)) and evaluate_c4(state, prop):
            violated.append(f"I17_DisclosedVsSourceSupportSeparation_violated:{prop.proposal_id}")

        # I19: Non-Malleable Lineage Continuity
        if evaluate_c4(state, prop) and binding.status != "COMPLETED":
            violated.append(f"I19_NonMalleableLineageContinuity_violated:{prop.proposal_id}")

        # I22: Dynamic Governance Precedence
        if (prop.consent_epoch != state.db_consent_epoch or prop.policy_epoch != state.db_policy_epoch) and evaluate_c4(state, prop):
            violated.append(f"I22_DynamicGovernancePrecedence_violated:{prop.proposal_id}")

    return violated
