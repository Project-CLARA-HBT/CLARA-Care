"""ML Lineage & Non-Downgrade Descendant Verifier.

Spec: PH06 / A04 (ML + Retrieval).
Enforces:
1. Anti-downgrade property across clinical proposal review chains.
2. Invariant: descendant proposals cannot reduce attestation level (L3 -> L0).
3. Preserves root model inference context bindings and source snapshot manifests.
"""

from __future__ import annotations

import dataclasses
from typing import Any

ATTESTATION_RANKS: dict[str, int] = {
    "APPLICATION_ENVELOPE_ONLY": 0,
    "SERVER_PRE_DISPATCH": 0,
    "TRANSPORT_DISPATCH": 1,
    "TRANSPORT_DISPATCH_ATTESTED": 1,
    "PROVIDER_RECEIPT_VERIFIED": 2,
    "PROVIDER_EXECUTION_ATTESTED": 3,
}


@dataclasses.dataclass(frozen=True)
class LineageVerificationResult:
    valid: bool
    reason: str
    parent_attestation: str
    descendant_attestation: str


class LineageAntiDowngradeVerifier:
    """Verifies that review descendants maintain or enhance provenance attestation."""

    @staticmethod
    def verify_no_downgrade(
        *,
        parent_attestation: str,
        descendant_attestation: str,
        parent_snapshot_id: str | None,
        descendant_snapshot_id: str | None,
    ) -> LineageVerificationResult:
        parent_rank = ATTESTATION_RANKS.get(parent_attestation, 0)
        descendant_rank = ATTESTATION_RANKS.get(descendant_attestation, 0)

        # 1. Attestation level non-downgrade check
        if descendant_rank < parent_rank:
            return LineageVerificationResult(
                valid=False,
                reason=f"Attestation downgrade forbidden: {descendant_attestation} < {parent_attestation}",
                parent_attestation=parent_attestation,
                descendant_attestation=descendant_attestation,
            )

        # 2. Source snapshot preservation check
        if parent_snapshot_id and descendant_snapshot_id != parent_snapshot_id:
            return LineageVerificationResult(
                valid=False,
                reason=f"Snapshot mismatch across descendant chain: {descendant_snapshot_id} != {parent_snapshot_id}",
                parent_attestation=parent_attestation,
                descendant_attestation=descendant_attestation,
            )

        return LineageVerificationResult(
            valid=True,
            reason="Lineage anti-downgrade invariant satisfied",
            parent_attestation=parent_attestation,
            descendant_attestation=descendant_attestation,
        )
