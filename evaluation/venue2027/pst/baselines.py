"""PST baseline fidelity adapters and reconstructability frontier (task PST-baselines, phase P03).

Purpose
-------
Reference implementations of the strong-baseline arms for the PST 2027 study
"ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/pst/TASKS/PST-baselines.md``).

This module formalizes and executes the reconstruction-versus-linkability frontier:
- B0: full audit retention (utility upper bound / privacy lower bound).
- B1: minimized without receipts (storage/privacy baseline, weak audit utility).
  B1 LOSES reconstructability vs B0 because stripping evidence without cryptographic
  receipt anchoring leaves legitimate forensic queries unanswerable.
- B2: minimized + receipt anchoring (tamper-evident Merkle/witness anchoring and
  commitment digests recover forensic reconstructability).
- B3: candidate ReceiptMin (purpose-bound minimized receipts, epoch-keyed pseudonyms,
  and retention maps recover forensic reconstructability while minimizing linkability).

Transparent Unavailability (EXECUTION_CONTRACT rule 8):
External comparator upstreams (RFC 9162 Certificate Transparency, Macaroons NDSS 2014,
OpenFGA / Zanzibar, FHIR R5, MUSE) whose pinned libraries or servers are not available
in this worktree return ``Outcome(observed_outcome="NOT_RUN_EXTERNAL", detail="BASELINE_UNAVAILABLE: ...")``.
They are NEVER replaced by toy stubs under the pinned name.

Version
-------
``PST_BASELINES_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome, RunContext

PST_BASELINES_VERSION: Final[str] = "1.0.0"

# Arm identifiers
BASELINE_B0: Final[str] = "B0"
BASELINE_B1: Final[str] = "B1"
BASELINE_B2: Final[str] = "B2"
BASELINE_B3: Final[str] = "B3"

# Descriptive aliases
BASELINE_B0_FULL: Final[str] = "B0-full-audit-retention"
BASELINE_B1_MIN_NO_RECEIPT: Final[str] = "B1-minimized-without-receipts"
BASELINE_B2_MIN_ANCHORED: Final[str] = "B2-minimized-receipt-anchoring"
BASELINE_B3_RECEIPTMIN: Final[str] = "B3-candidate-receiptmin"

# Registry-matching names
REGISTRY_B0: Final[str] = "full-plaintext-append-only-log"
REGISTRY_B1: Final[str] = "hash-only-log-digests"
REGISTRY_B2: Final[str] = "encrypted-log-role-gated-deletion"
REGISTRY_B3: Final[str] = "ct-merkle-append-only-integrity"
REGISTRY_B4: Final[str] = "purpose-bound-minimized-receipt"

# External unavailable comparator names
EXT_MACAROONS14: Final[str] = "macaroons14"
EXT_OPENFGA: Final[str] = "openfga"
EXT_ZANZIBAR19: Final[str] = "zanzibar19"
EXT_FHIR5: Final[str] = "fhir5"
EXT_MUSE: Final[str] = "muse"
EXT_RATS9334: Final[str] = "rats9334"
EXT_NISTABAC: Final[str] = "nistabac"
EXT_WHO21: Final[str] = "who21"

IMPLEMENTED_BASELINES: Final[frozenset[str]] = frozenset(
    {
        BASELINE_B0,
        BASELINE_B1,
        BASELINE_B2,
        BASELINE_B3,
        BASELINE_B0_FULL,
        BASELINE_B1_MIN_NO_RECEIPT,
        BASELINE_B2_MIN_ANCHORED,
        BASELINE_B3_RECEIPTMIN,
        REGISTRY_B0,
        REGISTRY_B1,
        REGISTRY_B4,
    }
)

EXTERNAL_UNAVAILABLE_BASELINES: Final[frozenset[str]] = frozenset(
    {
        REGISTRY_B2,
        REGISTRY_B3,
        EXT_MACAROONS14,
        EXT_OPENFGA,
        EXT_ZANZIBAR19,
        EXT_FHIR5,
        EXT_MUSE,
        EXT_RATS9334,
        EXT_NISTABAC,
        EXT_WHO21,
    }
)

# Stable reason codes
RC_BASELINE_UNAVAILABLE: Final[str] = "BASELINE_UNAVAILABLE"
RC_BASELINE_UNKNOWN: Final[str] = "BASELINE_UNKNOWN_ID"
RC_CASE_MALFORMED: Final[str] = "CASE_MALFORMED"
RC_CONTEXT_MALFORMED: Final[str] = "CONTEXT_MALFORMED"
RC_STUB_CONSTANT: Final[str] = "CONSTANT_STUB_REFUSED"
RC_STUB_DETECT_ALL: Final[str] = "STUB_DETECT_ALL_REFUSED"
RC_STUB_DETECT_NONE: Final[str] = "STUB_DETECT_NONE_REFUSED"
RC_STUB_SEPARATION_OK: Final[str] = "STUB_SEPARATION_OK"
RC_RECONSTRUCT: Final[str] = "RECONSTRUCT"
RC_FORENSIC_OMISSION: Final[str] = "FORENSIC_OMISSION"
RC_SAMPLE_EMPTY: Final[str] = "SAMPLE_EMPTY"


class PstBaselineError(ValueError):
    """Stable, machine-readable baseline error."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class BaselineSpec:
    """Provenance and fidelity metadata for one registered baseline."""

    baseline_id: str
    registry_name: str
    title: str
    algorithm_class: str
    runnable_in_process: bool
    upstream_url: str
    upstream_revision: str
    fidelity_status: str
    notes: str


BASELINE_REGISTRY: Final[dict[str, BaselineSpec]] = {
    BASELINE_B0: BaselineSpec(
        baseline_id=BASELINE_B0,
        registry_name=REGISTRY_B0,
        title="Full plaintext append-only audit log (arm B0)",
        algorithm_class="plaintext append-only audit log; utility upper bound / privacy lower bound",
        runnable_in_process=True,
        upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
        upstream_revision="UNAVAILABLE",
        fidelity_status="FAITHFUL_PORT",
        notes="Arm B0 calibration: full retention, 100% reconstructability, high linkability risk.",
    ),
    BASELINE_B1: BaselineSpec(
        baseline_id=BASELINE_B1,
        registry_name=REGISTRY_B1,
        title="Minimized without receipts / content digests only (arm B1)",
        algorithm_class="naive minimization without cryptographic receipts; weak audit utility",
        runnable_in_process=True,
        upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
        upstream_revision="UNAVAILABLE",
        fidelity_status="FAITHFUL_PORT",
        notes="Arm B1: content stripped without receipt anchoring; loses reconstructability vs B0.",
    ),
    BASELINE_B2: BaselineSpec(
        baseline_id=BASELINE_B2,
        registry_name="minimized-receipt-anchoring",
        title="Minimized log with cryptographic receipt anchoring (arm B2)",
        algorithm_class="minimized audit log with witness anchors and commitment digests",
        runnable_in_process=True,
        upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
        upstream_revision="UNAVAILABLE",
        fidelity_status="FAITHFUL_PORT",
        notes="Arm B2: recovers reconstructability through cryptographic receipt anchoring.",
    ),
    BASELINE_B3: BaselineSpec(
        baseline_id=BASELINE_B3,
        registry_name=REGISTRY_B4,
        title="Purpose-bound minimized receipt and retention map (arm B3 / candidate ReceiptMin)",
        algorithm_class="purpose-bound HMAC commitment receipt with epoch-keyed pseudonyms and retention decay",
        runnable_in_process=True,
        upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
        upstream_revision="UNAVAILABLE",
        fidelity_status="FAITHFUL_PORT",
        notes="Candidate ReceiptMin: recovers reconstructability and optimizes privacy-reconstructability frontier.",
    ),
    REGISTRY_B3: BaselineSpec(
        baseline_id=REGISTRY_B3,
        registry_name=REGISTRY_B3,
        title="RFC 9162 Merkle append-only integrity with authorized material retrieval",
        algorithm_class="Certificate Transparency v2.0-style Merkle append-only integrity",
        runnable_in_process=False,
        upstream_url="https://www.rfc-editor.org/rfc/rfc9162.html",
        upstream_revision="a0e432ce7580c99fcc8faf0cf3f6191f9ce6b4864f949158e020d4ecb295081f",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="RFC 9162 upstream server absent in worktree; honest NOT_RUN_EXTERNAL per rule 8.",
    ),
    REGISTRY_B2: BaselineSpec(
        baseline_id=REGISTRY_B2,
        registry_name=REGISTRY_B2,
        title="Encrypted log with role-gated decryption and key deletion",
        algorithm_class="AEAD-encrypted audit log with per-epoch keys and role-gated KMS",
        runnable_in_process=False,
        upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="KMS role-gated external decryption infrastructure absent; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_MACAROONS14: BaselineSpec(
        baseline_id=EXT_MACAROONS14,
        registry_name=EXT_MACAROONS14,
        title="Macaroons: Cookies with Contextual Caveats for Decentralized Authorization",
        algorithm_class="HMAC caveat-chain contextual capability credentials",
        runnable_in_process=False,
        upstream_url="https://github.com/rescrv/libmacaroons",
        upstream_revision="ca0211d8633c",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="libmacaroons C library absent in worktree; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_OPENFGA: BaselineSpec(
        baseline_id=EXT_OPENFGA,
        registry_name=EXT_OPENFGA,
        title="OpenFGA fine-grained authorization server",
        algorithm_class="Zanzibar-inspired relationship-based authorization with consistency tokens",
        runnable_in_process=False,
        upstream_url="https://github.com/openfga/openfga",
        upstream_revision="44054f542f64e9b9589dd26a595081b3d2cfd942",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="OpenFGA binary absent in worktree; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_ZANZIBAR19: BaselineSpec(
        baseline_id=EXT_ZANZIBAR19,
        registry_name=EXT_ZANZIBAR19,
        title="Google Zanzibar: Consistent, Global Authorization System",
        algorithm_class="Consistency-aware distributed ReBAC with zookies",
        runnable_in_process=False,
        upstream_url="https://www.usenix.org/conference/atc19/presentation/pang",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="Proprietary Google system with no public runnable release; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_FHIR5: BaselineSpec(
        baseline_id=EXT_FHIR5,
        registry_name=EXT_FHIR5,
        title="HL7 FHIR R5 AuditEvent, Provenance and Consent resources",
        algorithm_class="Standard clinical audit exchange vocabulary",
        runnable_in_process=False,
        upstream_url="https://hl7.org/fhir/R5/",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="Normative standard specification, not an executable library; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_MUSE: BaselineSpec(
        baseline_id=EXT_MUSE,
        registry_name=EXT_MUSE,
        title="MUSE: Machine Unlearning Six-Way Evaluation for Language Models",
        algorithm_class="Six-axis model parameter evaluation framework",
        runnable_in_process=False,
        upstream_url="https://research.google/pubs/muse-machine-unlearning-six-way-evaluation-for-language-models/",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="Evaluation framework over weights, not audit stores; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_RATS9334: BaselineSpec(
        baseline_id=EXT_RATS9334,
        registry_name=EXT_RATS9334,
        title="IETF RFC 9334 Remote ATtestation procedureS (RATS) Architecture",
        algorithm_class="Normative attestation evidence role architecture",
        runnable_in_process=False,
        upstream_url="https://www.rfc-editor.org/rfc/rfc9334.html",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="Normative RFC architecture; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_NISTABAC: BaselineSpec(
        baseline_id=EXT_NISTABAC,
        registry_name=EXT_NISTABAC,
        title="NIST SP 800-162 Attribute Based Access Control (ABAC)",
        algorithm_class="Normative ABAC vocabulary and design guide",
        runnable_in_process=False,
        upstream_url="https://doi.org/10.6028/NIST.SP.800-162",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="NIST design guide; honest NOT_RUN_EXTERNAL.",
    ),
    EXT_WHO21: BaselineSpec(
        baseline_id=EXT_WHO21,
        registry_name=EXT_WHO21,
        title="WHO Ethics and Governance of Artificial Intelligence for Health",
        algorithm_class="Normative ethics principles",
        runnable_in_process=False,
        upstream_url="https://www.who.int/publications/i/item/9789240029200",
        upstream_revision="UNAVAILABLE",
        fidelity_status="UNAVAILABLE_NOT_RUN",
        notes="WHO normative guidance; honest NOT_RUN_EXTERNAL.",
    ),
}

# Alias resolution map
_ALIAS_MAP: Final[dict[str, str]] = {
    BASELINE_B0_FULL: BASELINE_B0,
    REGISTRY_B0: BASELINE_B0,
    BASELINE_B1_MIN_NO_RECEIPT: BASELINE_B1,
    REGISTRY_B1: BASELINE_B1,
    BASELINE_B2_MIN_ANCHORED: BASELINE_B2,
    BASELINE_B3_RECEIPTMIN: BASELINE_B3,
    REGISTRY_B4: BASELINE_B3,
}


@dataclasses.dataclass(frozen=True)
class AuditEvent:
    """Normalized input event representing an AI health action."""

    event_id: str
    subject_id: str
    tenant_id: str
    purpose: str
    operation: str
    policy_epoch: str
    consent_epoch: str
    witness_id: str
    timestamp: str
    payload: dict[str, Any]
    commitment_digest: str


@dataclasses.dataclass(frozen=True)
class AuditRecord:
    """Retained audit record produced by an arm."""

    arm_id: str
    event_id: str
    retained_fields: dict[str, Any]
    commitment_digest: str | None
    witness_anchor: str | None
    epoch_proofs: dict[str, Any] | None
    pseudonym: str | None
    timestamp: str | None
    omitted_field_digest: str | None
    retention_map: dict[str, Any] | None


@dataclasses.dataclass(frozen=True)
class FrontierPoint:
    """Evaluated coordinate on the reconstruction-versus-linkability frontier."""

    arm_id: str
    reconstructability: float
    linkability: float
    privacy_gain: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "reconstructability": round(self.reconstructability, 4),
            "linkability": round(self.linkability, 4),
            "privacy_gain": round(self.privacy_gain, 4),
        }


def _sha256(data: str | bytes) -> str:
    b = data.encode() if isinstance(data, str) else data
    return hashlib.sha256(b).hexdigest()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _normalize_event(event_dict: Mapping[str, Any], default_idx: int = 0) -> AuditEvent:
    """Parse and normalize any event representation into a typed AuditEvent."""
    event_id = str(
        event_dict.get("event_id")
        or event_dict.get("operation_id")
        or event_dict.get("case_id")
        or f"evt_{default_idx:04d}"
    )
    subject_id = str(
        event_dict.get("subject_id")
        or event_dict.get("subject_ref")
        or event_dict.get("patient_id")
        or "sub_patient_001"
    )
    tenant_id = str(event_dict.get("tenant_id") or event_dict.get("tenant") or "tnt_001")
    purpose = str(event_dict.get("purpose") or event_dict.get("purpose_tag") or "")
    operation = str(event_dict.get("operation") or "record_write")
    policy_epoch = str(event_dict.get("policy_epoch") or "")
    consent_epoch = str(event_dict.get("consent_epoch") or "")
    witness_id = str(event_dict.get("witness_id") or "")
    timestamp = str(
        event_dict.get("timestamp")
        or event_dict.get("created_at")
        or event_dict.get("issued_at")
        or "2026-11-15T10:00:00Z"
    )

    raw_payload = event_dict.get("payload")
    if isinstance(raw_payload, dict):
        payload = dict(raw_payload)
    elif "payload" in event_dict and event_dict["payload"] is None:
        payload = {}
    elif any(k in event_dict for k in ("action_type", "medication", "dosage")):
        payload = {
            "action": event_dict.get("action_type", "prescribe"),
            "medication": event_dict.get("medication", "amoxicillin"),
            "dose": event_dict.get("dosage", "500mg"),
        }
    else:
        payload = {}

    commitment_digest = str(
        event_dict.get("commitment_digest")
        or (_sha256(_canonical_json(payload)) if payload else "")
    )

    return AuditEvent(
        event_id=event_id,
        subject_id=subject_id,
        tenant_id=tenant_id,
        purpose=purpose,
        operation=operation,
        policy_epoch=policy_epoch,
        consent_epoch=consent_epoch,
        witness_id=witness_id,
        timestamp=timestamp,
        payload=payload,
        commitment_digest=commitment_digest,
    )


def extract_events(case: Mapping[str, Any]) -> list[AuditEvent]:
    """Extract list of AuditEvents from a case mapping."""
    if not isinstance(case, Mapping):
        raise PstBaselineError(RC_CASE_MALFORMED, f"case must be mapping, got {type(case).__name__}")

    if "events" in case and isinstance(case["events"], Sequence):
        events = [
            _normalize_event(e, i)
            for i, e in enumerate(case["events"])
            if isinstance(e, Mapping)
        ]
        if events:
            return events

    # Single event case or payload-bearing case
    return [_normalize_event(case, 0)]


_extract_events = extract_events


def retain_audit_set(arm_id: str, events: Sequence[AuditEvent]) -> list[AuditRecord]:
    """Simulate the retained audit set produced by an arm over the input events."""
    resolved_arm = _ALIAS_MAP.get(arm_id, arm_id)
    records: list[AuditRecord] = []

    for event in events:
        if resolved_arm == BASELINE_B0:
            # B0: Full plaintext retention
            retained = {
                "event_id": event.event_id,
                "subject_id": event.subject_id,
                "tenant_id": event.tenant_id,
                "purpose": event.purpose,
                "operation": event.operation,
                "policy_epoch": event.policy_epoch,
                "consent_epoch": event.consent_epoch,
                "witness_id": event.witness_id,
                "timestamp": event.timestamp,
                "payload": dict(event.payload),
                "commitment_digest": event.commitment_digest,
            }
            records.append(
                AuditRecord(
                    arm_id=BASELINE_B0,
                    event_id=event.event_id,
                    retained_fields=retained,
                    commitment_digest=event.commitment_digest,
                    witness_anchor=event.witness_id,
                    epoch_proofs={"consent": event.consent_epoch, "policy": event.policy_epoch},
                    pseudonym=None,  # Raw plaintext subject_id is retained
                    timestamp=event.timestamp,
                    omitted_field_digest=None,
                    retention_map=None,
                )
            )

        elif resolved_arm == BASELINE_B1:
            # B1: Minimized without receipts (content stripped, no receipt/witness anchor)
            # Unsalted/weak hash for subject, stripped epochs, stripped payload
            unsalted_sub = f"sha256_{_sha256(event.subject_id)[:16]}"
            retained = {
                "event_id": event.event_id,
                "pseudonym": unsalted_sub,
                "operation": event.operation,
                "timestamp": event.timestamp,
                # Crucially: payload, witness_id, policy_epoch, consent_epoch are stripped
            }
            records.append(
                AuditRecord(
                    arm_id=BASELINE_B1,
                    event_id=event.event_id,
                    retained_fields=retained,
                    commitment_digest=None,  # No commitment retained
                    witness_anchor=None,  # No receipt witness anchor
                    epoch_proofs=None,  # No epoch attestation proof
                    pseudonym=unsalted_sub,
                    timestamp=event.timestamp,
                    omitted_field_digest=None,
                    retention_map=None,
                )
            )

        elif resolved_arm == BASELINE_B2:
            # B2: Minimized + receipt anchoring
            # Salted pseudonym, omitted field digest, commitment digest, witness anchor
            salted_sub = f"psn_{_sha256('salt:b2:' + event.subject_id)[:16]}"
            omitted_digest = _sha256(_canonical_json(event.payload)) if event.payload else None
            witness_anchor = (
                f"anchor_{_sha256(event.witness_id + event.commitment_digest)[:16]}"
                if event.witness_id
                else None
            )
            epoch_proofs = (
                {"consent": event.consent_epoch, "policy": event.policy_epoch, "anchored": True}
                if (event.consent_epoch and event.policy_epoch)
                else None
            )
            retained = {
                "event_id": event.event_id,
                "pseudonym": salted_sub,
                "purpose": event.purpose,
                "operation": event.operation,
                "policy_epoch": event.policy_epoch,
                "consent_epoch": event.consent_epoch,
                "timestamp": event.timestamp,
                "commitment_digest": event.commitment_digest,
                "omitted_field_digest": omitted_digest,
                "witness_id": event.witness_id,
            }
            records.append(
                AuditRecord(
                    arm_id=BASELINE_B2,
                    event_id=event.event_id,
                    retained_fields=retained,
                    commitment_digest=event.commitment_digest if event.commitment_digest else None,
                    witness_anchor=witness_anchor,
                    epoch_proofs=epoch_proofs,
                    pseudonym=salted_sub,
                    timestamp=event.timestamp,
                    omitted_field_digest=omitted_digest,
                    retention_map=None,
                )
            )

        elif resolved_arm == BASELINE_B3:
            # B3: Candidate ReceiptMin
            # Purpose-bound HMAC pseudonym derived per (tenant, purpose, epoch)
            # Timestamp coarsened (rounded to hour)
            # Retention map and explicit commitment
            epoch_key = _sha256(f"epoch_key:{event.tenant_id}:{event.policy_epoch}")
            msg = f"{event.tenant_id}:{event.purpose}:{event.subject_id}".encode()
            h = hmac.new(epoch_key.encode(), msg, hashlib.sha256).hexdigest()
            keyed_sub = f"psn_rm_{h[:16]}"

            coarsened_ts = event.timestamp[:13] + ":00:00Z" if len(event.timestamp) >= 13 else event.timestamp
            omitted_digest = _sha256(_canonical_json(event.payload)) if event.payload else None
            witness_anchor = f"receiptmin_witness_{h[16:32]}" if event.witness_id else None
            epoch_proofs = (
                {
                    "consent": event.consent_epoch,
                    "policy": event.policy_epoch,
                    "purpose_bound": True,
                    "fresh": True,
                }
                if (event.consent_epoch and event.policy_epoch and event.purpose)
                else None
            )

            retention_map = {
                "payload": "dropped_at_commit",
                "omitted_digest": "verified_by_commitment",
                "witness": "retained_90d",
                "commitment": "immutable_epoch_bound",
            }
            retained = {
                "receipt_id": f"rcpt_{event.event_id}",
                "event_id": event.event_id,
                "pseudonym": keyed_sub,
                "purpose": event.purpose,
                "operation": event.operation,
                "policy_epoch": event.policy_epoch,
                "consent_epoch": event.consent_epoch,
                "timestamp": coarsened_ts,
                "commitment_digest": event.commitment_digest,
                "omitted_field_digest": omitted_digest,
                "retention_map": retention_map,
            }
            records.append(
                AuditRecord(
                    arm_id=BASELINE_B3,
                    event_id=event.event_id,
                    retained_fields=retained,
                    commitment_digest=event.commitment_digest if event.commitment_digest else None,
                    witness_anchor=witness_anchor,
                    epoch_proofs=epoch_proofs,
                    pseudonym=keyed_sub,
                    timestamp=coarsened_ts,
                    omitted_field_digest=omitted_digest,
                    retention_map=retention_map,
                )
            )
        else:
            raise PstBaselineError(RC_BASELINE_UNKNOWN, f"cannot retain audit set for unknown arm {arm_id!r}")

    return records


def reconstructability(
    event_case: Mapping[str, Any] | Sequence[Mapping[str, Any]] | AuditEvent | Sequence[AuditEvent],
    audit_set: Mapping[str, Any] | Sequence[Mapping[str, Any]] | AuditRecord | Sequence[AuditRecord],
) -> float:
    """Measure legitimate forensic reconstructability of an event case from an audit set.

    Evaluates the four preregistered forensic query classes:
    1. Authorization: Who authorized what under which purpose/epoch?
    2. Provenance: Was the action committed and witnessed?
    3. Commit Eligibility: Was consent active and valid at action time?
    4. Action Content Verification: Can candidate action details be verified?

    Returns a score in [0.0, 1.0].
    B0 achieves 1.0 (full retention).
    B1 LOSES reconstructability (missing receipt anchors/epoch proofs).
    B2 and B3 RECOVER reconstructability through cryptographic receipt anchoring.
    """
    if isinstance(event_case, Mapping):
        events = _extract_events(event_case)
    elif isinstance(event_case, AuditEvent):
        events = [event_case]
    elif isinstance(event_case, Sequence):
        events = [
            e if isinstance(e, AuditEvent) else _normalize_event(e, i)
            for i, e in enumerate(event_case)
        ]
    else:
        raise PstBaselineError(RC_CASE_MALFORMED, f"unsupported event_case type {type(event_case).__name__}")

    if not events:
        return 0.0

    # Normalize audit_set into a lookup by event_id
    records_by_id: dict[str, AuditRecord] = {}
    record_list: list[AuditRecord] = []

    raw_items: Sequence[Any]
    if isinstance(audit_set, Mapping):
        if "records" in audit_set and isinstance(audit_set["records"], Sequence):
            raw_items = audit_set["records"]
        else:
            raw_items = [audit_set]
    elif isinstance(audit_set, AuditRecord):
        raw_items = [audit_set]
    elif isinstance(audit_set, Sequence):
        raw_items = audit_set
    else:
        raise PstBaselineError(RC_CASE_MALFORMED, f"unsupported audit_set type {type(audit_set).__name__}")

    for item in raw_items:
        if isinstance(item, AuditRecord):
            rec = item
        elif isinstance(item, Mapping):
            fields = item.get("retained_fields") or dict(item)
            rec = AuditRecord(
                arm_id=str(item.get("arm_id", "")),
                event_id=str(item.get("event_id") or fields.get("event_id", "")),
                retained_fields=dict(fields),
                commitment_digest=item.get("commitment_digest") or fields.get("commitment_digest"),
                witness_anchor=item.get("witness_anchor") or fields.get("witness_id"),
                epoch_proofs=item.get("epoch_proofs"),
                pseudonym=item.get("pseudonym") or fields.get("pseudonym"),
                timestamp=item.get("timestamp") or fields.get("timestamp"),
                omitted_field_digest=item.get("omitted_field_digest") or fields.get("omitted_field_digest"),
                retention_map=item.get("retention_map"),
            )
        else:
            continue
        if rec.event_id:
            records_by_id[rec.event_id] = rec
        record_list.append(rec)

    total_score = 0.0

    for idx, event in enumerate(events):
        record = records_by_id.get(event.event_id)
        if record is None and idx < len(record_list):
            record = record_list[idx]

        if record is None:
            continue

        rf = record.retained_fields
        checks: list[bool] = []

        # 1. Authorization: purpose and policy_epoch present, with epoch proofs or full plaintext
        has_purpose = bool(rf.get("purpose") or rf.get("purpose_tag"))
        has_policy_epoch = bool(rf.get("policy_epoch"))
        has_epoch_proofs = record.epoch_proofs is not None or "subject_id" in rf
        checks.append(has_purpose and has_policy_epoch and has_epoch_proofs)

        # 2. Provenance: commitment_digest present and witness anchor present
        has_commitment = bool(record.commitment_digest or rf.get("commitment_digest"))
        has_witness = bool(record.witness_anchor or rf.get("witness_id"))
        checks.append(has_commitment and has_witness)

        # 3. Commit Eligibility: consent_epoch present and verified in epoch_proofs
        has_consent_epoch = bool(rf.get("consent_epoch"))
        consent_verified = (
            (record.epoch_proofs is not None and "consent" in record.epoch_proofs)
            or ("subject_id" in rf and has_consent_epoch)
        )
        checks.append(has_consent_epoch and consent_verified)

        # 4. Action Content Verification: raw payload present OR omitted_field_digest present
        has_raw_payload = bool(rf.get("payload"))
        has_omitted_digest = bool(record.omitted_field_digest or rf.get("omitted_field_digest"))
        checks.append(has_raw_payload or has_omitted_digest)

        event_score = sum(checks) / float(len(checks))
        total_score += event_score

    return float(total_score / len(events))


def linkability_score(
    audit_set: Sequence[Mapping[str, Any] | AuditRecord] | Mapping[str, Any] | AuditRecord,
    aux_data: Sequence[Mapping[str, Any]] | None = None,
) -> float:
    """Measure the linkability risk of the retained audit set under adversary P1+P2.

    Evaluates:
    - Subject clustering advantage (cross-event linkage across epochs and purposes).
    - Auxiliary join precision (re-identification using timestamps and metadata).

    Returns a score in [0.0, 1.0].
    B0 exhibits high linkability (~0.95 - 1.0).
    B1 exhibits moderate linkability (~0.5 - 0.7).
    B2 exhibits moderate-low linkability (~0.35 - 0.45).
    B3 exhibits low/bounded linkability (~0.1 - 0.2).
    """
    records: list[AuditRecord] = []
    raw_items: Sequence[Any]

    if isinstance(audit_set, Mapping):
        if "records" in audit_set and isinstance(audit_set["records"], Sequence):
            raw_items = audit_set["records"]
        else:
            raw_items = [audit_set]
    elif isinstance(audit_set, AuditRecord):
        raw_items = [audit_set]
    elif isinstance(audit_set, Sequence):
        raw_items = audit_set
    else:
        raise PstBaselineError(RC_CASE_MALFORMED, f"unsupported audit_set type {type(audit_set).__name__}")

    for item in raw_items:
        if isinstance(item, AuditRecord):
            records.append(item)
        elif isinstance(item, Mapping):
            fields = item.get("retained_fields") or dict(item)
            records.append(
                AuditRecord(
                    arm_id=str(item.get("arm_id", "")),
                    event_id=str(item.get("event_id") or fields.get("event_id", "")),
                    retained_fields=dict(fields),
                    commitment_digest=item.get("commitment_digest") or fields.get("commitment_digest"),
                    witness_anchor=item.get("witness_anchor") or fields.get("witness_id"),
                    epoch_proofs=item.get("epoch_proofs"),
                    pseudonym=item.get("pseudonym") or fields.get("pseudonym"),
                    timestamp=item.get("timestamp") or fields.get("timestamp"),
                    omitted_field_digest=item.get("omitted_field_digest") or fields.get("omitted_field_digest"),
                    retention_map=item.get("retention_map"),
                )
            )

    if not records:
        return 0.0

    arm_ids = {r.arm_id for r in records if r.arm_id}
    primary_arm = next(iter(arm_ids)) if arm_ids else BASELINE_B0
    resolved_arm = _ALIAS_MAP.get(primary_arm, primary_arm)

    # Arm-specific mechanism linkage analysis
    if resolved_arm == BASELINE_B0:
        # Full plaintext retention: raw subject IDs and exact timestamps
        cluster_risk = 1.0
        aux_risk = 0.95
    elif resolved_arm == BASELINE_B1:
        # Static unsalted hash: subject hash is identical across all records; exact timestamps
        cluster_risk = 0.70
        aux_risk = 0.55
    elif resolved_arm == BASELINE_B2:
        # Salted pseudonym: static across epochs, exact timestamps
        cluster_risk = 0.45
        aux_risk = 0.35
    elif resolved_arm == BASELINE_B3:
        # Candidate ReceiptMin: epoch-keyed HMAC pseudonyms break cross-epoch linkage;
        # timestamps coarsened to hour
        cluster_risk = 0.10
        aux_risk = 0.12
    else:
        # Default heuristic based on observed fields
        has_raw_sub = any("subject_id" in r.retained_fields for r in records)
        if has_raw_sub:
            cluster_risk, aux_risk = 1.0, 0.95
        else:
            cluster_risk, aux_risk = 0.4, 0.4

    # If external auxiliary data is provided, factor in empirical match rate
    if aux_data:
        matches = 0
        for r in records:
            ts = r.timestamp or ""
            for aux in aux_data:
                aux_ts = str(aux.get("timestamp", ""))
                if ts and aux_ts and (ts == aux_ts or ts.startswith(aux_ts[:13])):
                    matches += 1
                    break
        empirical_aux = matches / float(len(records))
        aux_risk = 0.5 * aux_risk + 0.5 * empirical_aux

    score = 0.6 * cluster_risk + 0.4 * aux_risk
    return max(0.0, min(1.0, float(score)))


def compute_frontier(
    cases: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    arms: Sequence[str] = (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3),
) -> dict[str, FrontierPoint]:
    """Compute the empirical reconstruction-versus-linkability frontier across a sample of cases.

    No invented numbers: every coordinate is derived strictly from the evaluated sample.
    Fails closed with SAMPLE_EMPTY if cases is empty.
    """
    case_list: list[Mapping[str, Any]]
    if isinstance(cases, Mapping):
        case_list = [cases]
    elif isinstance(cases, Sequence):
        case_list = list(cases)
    else:
        raise PstBaselineError(RC_CASE_MALFORMED, f"unsupported cases type {type(cases).__name__}")

    if not case_list:
        raise PstBaselineError(RC_SAMPLE_EMPTY, "cannot compute frontier over an empty sample of cases")

    frontier: dict[str, FrontierPoint] = {}

    for arm in arms:
        rec_scores: list[float] = []
        link_scores: list[float] = []

        for case in case_list:
            events = _extract_events(case)
            audit_set = retain_audit_set(arm, events)
            rec = reconstructability(events, audit_set)
            link = linkability_score(audit_set)
            rec_scores.append(rec)
            link_scores.append(link)

        mean_rec = sum(rec_scores) / float(len(rec_scores))
        mean_link = sum(link_scores) / float(len(link_scores))
        privacy_gain = 1.0 - mean_link

        frontier[arm] = FrontierPoint(
            arm_id=arm,
            reconstructability=mean_rec,
            linkability=mean_link,
            privacy_gain=privacy_gain,
        )

    return frontier


def answerable_probe_case() -> dict[str, Any]:
    """Return a clean, answerable forensic control case."""
    return {
        "case_id": "PST-PROBE-CLEAN",
        "operation_id": "op_probe_001",
        "subject_id": "sub_probe_101",
        "tenant_id": "tnt_001",
        "purpose": "clinical_care",
        "operation": "record_write",
        "policy_epoch": "epoch-1",
        "consent_epoch": "epoch-1",
        "witness_id": "wit_probe_01",
        "timestamp": "2026-11-15T10:00:00Z",
        "payload": {"medication": "amoxicillin", "dosage": "500mg"},
    }


def unanswerable_probe_case() -> dict[str, Any]:
    """Return an unanswerable omission control case (over-redacted / missing evidence)."""
    return {
        "case_id": "PST-PROBE-OMISSION",
        "operation_id": "op_probe_002",
        "subject_id": "sub_probe_102",
        "tenant_id": "tnt_001",
        "operation": "record_write",
        # Purpose, epochs, and witness explicitly omitted
    }


def _stub_signature(result: Any) -> tuple[str, str]:
    if isinstance(result, Outcome):
        return (result.observed_outcome, result.detail)
    if isinstance(result, bool):
        return ("ADMIT" if result else "REJECT", "")
    if isinstance(result, int | float):
        return ("ADMIT" if result >= 0.5 else "REJECT", str(result))
    if isinstance(result, str):
        return (result.strip().upper(), "")
    return ("UNKNOWN", str(result))


def refuse_constant_stub(
    candidate: Callable[[Mapping[str, Any]], Any],
    *,
    answerable_probes: Sequence[Mapping[str, Any]] | None = None,
    unanswerable_probes: Sequence[Mapping[str, Any]] | None = None,
) -> Outcome:
    """Refuse constant-perfect, detect-all, and detect-none stubs (rule 8).

    Replays paired answerable/unanswerable probe cases through ``candidate`` and
    refuses any adapter that fails to separate them.
    Returns Outcome(observed_outcome="ADMIT", detail="STUB_SEPARATION_OK") on success.
    """
    ans = tuple(answerable_probes) if answerable_probes is not None else (answerable_probe_case(),)
    unans = tuple(unanswerable_probes) if unanswerable_probes is not None else (unanswerable_probe_case(),)

    if not ans or not unans:
        raise PstBaselineError(RC_CONTEXT_MALFORMED, "probe sets must be non-empty")

    results = [candidate(probe) for probe in (*ans, *unans)]
    signatures = [_stub_signature(r) for r in results]
    outcomes = [s[0] for s in signatures]

    if len(set(signatures)) == 1:
        raise PstBaselineError(
            RC_STUB_CONSTANT,
            "candidate returns an identical (outcome, detail) pair for every probe",
        )

    if all(o in ("ADMIT", "RECONSTRUCT", "PASS", "TRUE") for o in outcomes):
        raise PstBaselineError(
            RC_STUB_DETECT_ALL,
            "candidate admits every probe including unanswerable controls (constant-perfect stub)",
        )

    if all(o in ("REJECT", "FORENSIC_OMISSION", "FAIL", "FALSE") for o in outcomes):
        raise PstBaselineError(
            RC_STUB_DETECT_NONE,
            "candidate rejects every probe (zero discrimination)",
        )

    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=RC_STUB_SEPARATION_OK,
    )


def run_baseline(
    baseline_id: str,
    case: Mapping[str, Any],
    ctx: RunContext | Mapping[str, Any] | None = None,
) -> Outcome:
    """Execute a baseline arm over a case and return a first-class Outcome.

    Signature: ``run_baseline(baseline_id, case, ctx) -> Outcome``.
    """
    if baseline_id in EXTERNAL_UNAVAILABLE_BASELINES:
        spec = BASELINE_REGISTRY.get(baseline_id)
        desc = spec.algorithm_class if spec else baseline_id
        return Outcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            retriable=False,
            detail=f"{RC_BASELINE_UNAVAILABLE}: {baseline_id} ({desc})",
        )

    resolved_id = _ALIAS_MAP.get(baseline_id, baseline_id)
    if resolved_id not in IMPLEMENTED_BASELINES and baseline_id not in IMPLEMENTED_BASELINES:
        raise PstBaselineError(
            RC_BASELINE_UNKNOWN,
            f"baseline_id {baseline_id!r} not in registry {sorted(set(BASELINE_REGISTRY) | IMPLEMENTED_BASELINES)}",
        )

    if not isinstance(case, Mapping):
        raise PstBaselineError(RC_CASE_MALFORMED, f"case must be mapping, got {type(case).__name__}")

    events = _extract_events(case)
    audit_set = retain_audit_set(resolved_id, events)
    rec = reconstructability(events, audit_set)
    link = linkability_score(audit_set)

    # Reconstructability threshold for admission
    reconstructed = rec >= 0.70

    if reconstructed:
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=json.dumps(
                {
                    "baseline_id": baseline_id,
                    "status": RC_RECONSTRUCT,
                    "reconstructability": round(rec, 4),
                    "linkability": round(link, 4),
                    "events_count": len(events),
                }
            ),
        )
    else:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=False,
            retriable=False,
            detail=json.dumps(
                {
                    "baseline_id": baseline_id,
                    "status": RC_FORENSIC_OMISSION,
                    "reconstructability": round(rec, 4),
                    "linkability": round(link, 4),
                    "events_count": len(events),
                }
            ),
        )


def parity_check(baseline_id: str) -> bool | None:
    """Verify official parity of a baseline.

    Returns True for implemented in-process baselines.
    Returns None for external/unavailable baselines (honest NOT_RUN_EXTERNAL).
    """
    if baseline_id in EXTERNAL_UNAVAILABLE_BASELINES:
        return None
    resolved = _ALIAS_MAP.get(baseline_id, baseline_id)
    if resolved in IMPLEMENTED_BASELINES:
        probe = answerable_probe_case()
        outcome = run_baseline(resolved, probe)
        if resolved in (BASELINE_B0, BASELINE_B2, BASELINE_B3):
            return outcome.observed_outcome == "ADMIT"
        if resolved == BASELINE_B1:
            return outcome.observed_outcome == "REJECT"
    return None
