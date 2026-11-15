"""Synthetic evidence-claim fixture records for ACNS-baselines (synthetic-acns-2027).

Purpose
-------
Pinned, deterministic synthetic records over which the four EVIDENCE-BOUNDARY
reference classes classify attestation claims. No PHI/PII, no network, no
clock: every record is a literal. Variants:

- ``bound``      — every claim dimension carries a bound receipt/attestation.
- ``downgraded`` — a provider receipt is quoted as proof of *execution*
                   (threat-model family ``model_agency``, gap G2): exactly the
                   downgrade gap that B0/B1/B2 must fail to detect and B3 must
                   detect.
- ``unbound``    — a claim carries no evidence binding at all (gap G7/G9).
- ``replayed``   — a receipt exists and is referenced but is bound to another
                   claim (gap G4): B1 sees "receipt present" and accepts; B3
                   must detect the transplant.

Failure semantics: pure data only; a malformed record would fail closed in
``baselines.load_reference_records`` / ``run_baseline``.
"""

from __future__ import annotations

SYNTHETIC_FIXTURES_VERSION = "1.0.0"
FIXTURE_DATASET = "synthetic-acns-2027"

_R1_BOUND = {
    "receipt_id": "rcpt-r1",
    "bound_to_claim_id": "claim-exec-1",
    "digest_binding": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "schedule_checked_at_rely_time": True,
}

# Unbound variant: the execution claim cites nothing.
_R2_UNBOUND: dict[str, dict[str, object]] = {}

# Replayed variant: the receipt is bound to the OTHER claim (transplanted).
_R3_REPLAYED = {
    "receipt_id": "rcpt-r3",
    "bound_to_claim_id": "claim-receipt-3",
    "digest_binding": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
    "schedule_checked_at_rely_time": True,
}

SYNTHETIC_CLAIM_RECORDS: dict[tuple[str, str], dict[str, object]] = {
    ("sok-claim-record-1", "bound"): {
        "record_id": "sok-claim-record-1",
        "variant": "bound",
        "receipts": {"rcpt-r1": _R1_BOUND},
        "claims_case": {
            "claims": [
                {
                    "claim_id": "claim-exec-1",
                    "dimension": "execution",
                    "asserted_level": "L3-EXECUTED",
                    "evidence_bindings": [
                        {
                            "dimension": "execution",
                            "binding_kind": "attested-bound",
                            "receipt_id": "rcpt-r1",
                        }
                    ],
                    "attested_execution": True,
                    "schedule_checked_at_rely_time": True,
                    "timestamp": "2026-11-15T00:00:00Z",
                }
            ]
        },
    },
    ("sok-claim-record-2", "downgraded"): {
        "record_id": "sok-claim-record-2",
        "variant": "downgraded",
        "receipts": {"rcpt-r2": {"receipt_id": "rcpt-r2", "bound_to_claim_id": "claim-exec-2"}},
        "claims_case": {
            "claims": [
                {
                    "claim_id": "claim-exec-2",
                    "dimension": "execution",
                    "asserted_level": "L3-EXECUTED",
                    # Receipt IS bound, but no attested_execution anchor: a
                    # receipt alone caps execution claims at L2 (gap G2).
                    "evidence_bindings": [
                        {
                            "dimension": "execution",
                            "binding_kind": "receipt-bound",
                            "receipt_id": "rcpt-r2",
                        }
                    ],
                    "attested_execution": False,
                    "schedule_checked_at_rely_time": True,
                    "timestamp": "2026-11-15T00:00:00Z",
                }
            ]
        },
    },
    ("sok-claim-record-3", "unbound"): {
        "record_id": "sok-claim-record-3",
        "variant": "unbound",
        "receipts": _R2_UNBOUND,
        "claims_case": {
            "claims": [
                {
                    "claim_id": "claim-receipt-3",
                    "dimension": "receipt",
                    "asserted_level": "L2-ACKNOWLEDGED",
                    "evidence_bindings": [],
                    "attested_execution": False,
                    "schedule_checked_at_rely_time": False,
                    "timestamp": "2026-11-15T00:00:00Z",
                }
            ]
        },
    },
    ("sok-claim-record-4", "replayed"): {
        "record_id": "sok-claim-record-4",
        "variant": "replayed",
        "receipts": {"rcpt-r3": _R3_REPLAYED},
        "claims_case": {
            "claims": [
                {
                    "claim_id": "claim-exec-4",
                    "dimension": "execution",
                    "asserted_level": "L3-EXECUTED",
                    # Receipt present and referenced, but bound to a different
                    # claim: signature-valid, context-invalid (gap G4).
                    "evidence_bindings": [
                        {
                            "dimension": "execution",
                            "binding_kind": "receipt-bound",
                            "receipt_id": "rcpt-r3",
                        }
                    ],
                    "attested_execution": False,
                    "schedule_checked_at_rely_time": True,
                    "timestamp": "2026-11-15T00:00:00Z",
                }
            ]
        },
    },
}
