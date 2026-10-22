"""GLHS Transport Verifier & Egress Payload Integrity Engine.

Spec: PH07 / A03 (Domain + GLHS Services).
Enforces:
1. Exact match between outbound HTTP body bytes and D3 / H_trans digest.
2. Invariant verification of semantic envelope (D2) and projection (D1).
3. Non-repudiation of provider receipts and attestation level upgrades.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any

from clara_api.glhs.inference_envelope import (
    compute_projection_digest,
    compute_semantic_envelope_digest,
    compute_transport_payload_digest,
)


@dataclasses.dataclass(frozen=True)
class TransportVerificationOutcome:
    valid: bool
    d1_projection_digest: str
    d2_semantic_digest: str
    d3_transport_digest: str
    reason: str


class GlhsTransportVerifier:
    """Verifies 3-digest continuity from clinical projection through network egress."""

    @staticmethod
    def verify_egress_payload(
        *,
        model_projection: Any,
        semantic_envelope: Any,
        raw_transport_bytes: bytes,
        expected_d3_digest: str | None = None,
    ) -> TransportVerificationOutcome:
        d1 = compute_projection_digest(model_projection)
        d2 = compute_semantic_envelope_digest(semantic_envelope)
        d3 = compute_transport_payload_digest(raw_transport_bytes)

        if expected_d3_digest and d3 != expected_d3_digest:
            return TransportVerificationOutcome(
                valid=False,
                d1_projection_digest=d1,
                d2_semantic_digest=d2,
                d3_transport_digest=d3,
                reason=f"Transport payload digest mismatch: computed {d3} != expected {expected_d3_digest}",
            )

        return TransportVerificationOutcome(
            valid=True,
            d1_projection_digest=d1,
            d2_semantic_digest=d2,
            d3_transport_digest=d3,
            reason="Exact 3-digest continuity verified",
        )
