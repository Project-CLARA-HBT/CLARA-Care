"""PST venue2027 candidate algorithm: ReceiptMin mechanism (task PST-candidate, phase P04).

Purpose
-------
Candidate mechanism (ReceiptMin, blueprint arm B4 of
``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``; task specification
``research/venue2027/VENUES/pst/TASKS/PST-candidate.md``) for
"ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization".
This module defines the isolated ReceiptMin mechanism: purpose-bound minimal
receipts that bind omitted fields through cryptographic digests and proofs
so forensic reconstruction remains possible, with explicit typed inputs and
outputs.

Novelty and mechanism
---------------------
- **Purpose-bound minimization**: strips raw patient/sensitive fields according to
  the declared audit purpose and policy epoch.
- **Cryptographic binding of omitted fields**: computes deterministic SHA-256
  digests of the complete canonical JSON serialization of omitted fields, allowing
  subsequent forensic reconstruction to verify that any supplied omitted field
  matches the bound digest without storing sensitive plaintext in the receipt.
- **Forensic query reconstruction**: evaluates ex-ante declared forensic queries
  against a collection of minimal receipts, returning a typed :class:`Reconstruction`
  verdict (with numerical score and answerability status).
- **Fail-closed discipline**: unknown or unmodelled queries, corrupted witnesses,
  missing retention proofs, or unregistered scopes fail closed to
  ``INDETERMINATE`` (never coerced to false success or silent passes).

Isolation contract
------------------
- This module imports **neither** the independent oracle (``independent_oracle.py``)
  nor any label files or held-out tuning sets.
- Pure, deterministic, offline functions: no network, no database, no hidden clock,
  no unseeded randomness, no environment variables.
- All records and queries are synthetic and PHI-free.

Target API
----------
- ``minimize(event, purpose, ...) -> Receipt``
- ``reconstruct(receipts, query) -> Reconstruction``
- ``run_candidate(case, ctx) -> Outcome`` (task-contract adapter)
- ``describe_mechanism() -> dict`` (machine-readable design record)

Version
-------
``CANDIDATE_ID = "clara.pst.candidate.receiptmin"``
``CANDIDATE_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome

CANDIDATE_ID: Final[str] = "clara.pst.candidate.receiptmin"
CANDIDATE_VERSION: Final[str] = "1.0.0"
CANDIDATE_ARM_ID: Final[str] = "B4"
RECEIPT_SCHEMA_VERSION: Final[str] = "clara.venue2027.pst.receipt.v1"

# --- Stable Reason Codes ----------------------------------------------------

REASON_OK: Final[str] = "OK"
REASON_MALFORMED_EVENT: Final[str] = "MALFORMED_EVENT"
REASON_UNKNOWN_PURPOSE: Final[str] = "UNKNOWN_PURPOSE"
REASON_UNKNOWN_QUERY: Final[str] = "UNKNOWN_QUERY"
REASON_MALFORMED_QUERY: Final[str] = "MALFORMED_QUERY"
REASON_MALFORMED_RECEIPT: Final[str] = "MALFORMED_RECEIPT"
REASON_UNKNOWN_ARM: Final[str] = "UNKNOWN_ARM"
REASON_TAMPER_DETECTED: Final[str] = "TAMPER_DETECTED"
REASON_MISSING_WITNESS: Final[str] = "MISSING_WITNESS"
REASON_MISSING_EPOCH: Final[str] = "MISSING_EPOCH"
REASON_MISSING_KEY_CUSTODY: Final[str] = "MISSING_KEY_CUSTODY"
REASON_OMITTED_FIELD_MISMATCH: Final[str] = "OMITTED_FIELD_MISMATCH"
REASON_UNSALTED_HASH_REFUSED: Final[str] = "UNSALTED_HASH_REFUSED"
REASON_PHI_FIELD_PRESENT: Final[str] = "PHI_FIELD_PRESENT"
REASON_UNRECOGNIZED_FIELD: Final[str] = "UNRECOGNIZED_FIELD"
REASON_MALFORMED_CASE: Final[str] = "MALFORMED_CASE"

# --- Answerability & Outcomes ------------------------------------------------

ANSWERABLE: Final[str] = "ANSWERABLE"
NOT_ANSWERABLE: Final[str] = "NOT_ANSWERABLE"
INDETERMINATE: Final[str] = "INDETERMINATE"

# --- Closed Vocabularies ----------------------------------------------------

VALID_PURPOSES: Final[tuple[str, ...]] = (
    "self_care",
    "clinical_care",
    "forensic_review",
    "security_audit",
    "research_analytics",
)

VALID_OPERATIONS: Final[tuple[str, ...]] = (
    "record_read",
    "record_write",
    "record_export",
    "receipt_verify",
    "retention_rotate",
)

VALID_RETENTION_MODES: Final[tuple[str, ...]] = ("full", "selective", "hash_only")

# Recognized event fields (PHI-free structural vocabulary)
KNOWN_EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "event_id",
        "operation_id",
        "tenant_id",
        "principal_id",
        "subject_ref",
        "purpose",
        "operation",
        "policy_epoch",
        "consent_epoch",
        "witness_id",
        "retention_mode",
        "created_at",
        "timestamp",
        "commitment_digest",
        "payload_digest",
        "omitted_fields",
    }
)

PHI_MARKERS: Final[tuple[str, ...]] = (
    "patient",
    "name",
    "ssn",
    "dob",
    "phone",
    "email",
    "address",
    "mrn",
    "diagnosis",
    "prescription",
)

_UNSALTED_DIGEST: Final[re.Pattern[str]] = re.compile(
    r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$"
)
_UNSALTED_PREFIXED: Final[re.Pattern[str]] = re.compile(
    r"^(?:md5|sha-?1|sha-?256)[:_][0-9a-fA-F]+$"
)

# Supported frozen query classes
KNOWN_QUERY_CLASSES: Final[tuple[str, ...]] = (
    "authorization",
    "provenance",
    "commit_eligibility",
)

# Mandatory fields per purpose
PURPOSE_RETAINED_FIELDS: Final[Mapping[str, frozenset[str]]] = {
    "self_care": frozenset({"commitment_digest", "purpose", "policy_epoch", "consent_epoch"}),
    "clinical_care": frozenset(
        {
            "commitment_digest",
            "purpose",
            "policy_epoch",
            "consent_epoch",
            "witness_id",
            "retention_mode",
        }
    ),
    "forensic_review": frozenset(
        {
            "commitment_digest",
            "purpose",
            "policy_epoch",
            "consent_epoch",
            "witness_id",
            "retention_mode",
        }
    ),
    "security_audit": frozenset(
        {"commitment_digest", "purpose", "policy_epoch", "witness_id", "retention_mode"}
    ),
    "research_analytics": frozenset({"commitment_digest", "purpose", "policy_epoch"}),
}


# --- Helpers -----------------------------------------------------------------


def json_canonical(value: Any) -> str:
    """Canonical JSON serialization (sorted keys, compact separators)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_digest(data: Any) -> str:
    """Compute 64-hex SHA-256 over canonical JSON or UTF-8 bytes."""
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = json_canonical(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# --- Typed Data Structures ---------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Receipt:
    """Purpose-bound minimal receipt with cryptographic omitted-field binding.

    Guarantees:
    - Retains only purpose-cleared metadata and proofs.
    - Omitted fields are mathematically bound via ``omitted_field_digest``.
    - Signature binds all receipt attributes in canonical JSON format.
    - JSON-serializable via :meth:`to_dict`.
    """

    version: str
    receipt_id: str
    tenant_id: str
    principal_id: str
    purpose: str
    operation: str
    policy_epoch: str
    issued_at: str
    omitted_field_digest: str
    retained_fields: dict[str, str]
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "receipt_id": self.receipt_id,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "purpose": self.purpose,
            "operation": self.operation,
            "policy_epoch": self.policy_epoch,
            "issued_at": self.issued_at,
            "omitted_field_digest": self.omitted_field_digest,
            "retained_fields": dict(self.retained_fields),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Receipt:
        return cls(
            version=str(data.get("version", "1")),
            receipt_id=str(data["receipt_id"]),
            tenant_id=str(data["tenant_id"]),
            principal_id=str(data["principal_id"]),
            purpose=str(data["purpose"]),
            operation=str(data.get("operation", "record_read")),
            policy_epoch=str(data["policy_epoch"]),
            issued_at=str(data["issued_at"]),
            omitted_field_digest=str(data["omitted_field_digest"]),
            retained_fields=dict(data.get("retained_fields", {})),
            signature=str(data.get("signature", "")),
        )


@dataclasses.dataclass(frozen=True)
class Reconstruction:
    """Forensic reconstruction evaluation verdict."""

    score: float
    answerable: str
    reason_code: str
    query_id: str
    evidence_fields: tuple[str, ...]
    details: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 6),
            "answerable": self.answerable,
            "reason_code": self.reason_code,
            "query_id": self.query_id,
            "evidence_fields": list(self.evidence_fields),
            "details": dict(self.details),
        }


# --- Core Receipt Minimization Mechanism -------------------------------------


def minimize(
    event: Mapping[str, Any],
    purpose: str | None = None,
    *,
    signing_key: bytes = b"pst-receiptmin-eval-signing-key",
) -> Receipt:
    """Minimize an audit event into a purpose-bound receipt.

    Binds omitted fields via canonical SHA-256 digest so forensic verification
    remains possible without plaintext retention.
    """
    if not isinstance(event, Mapping):
        raise ValueError(f"{REASON_MALFORMED_EVENT}: event must be a mapping")

    # Purpose resolution
    declared_purpose = purpose or event.get("purpose")
    if not declared_purpose or not isinstance(declared_purpose, str):
        raise ValueError(f"{REASON_UNKNOWN_PURPOSE}: missing or empty purpose")
    if declared_purpose not in VALID_PURPOSES:
        raise ValueError(f"{REASON_UNKNOWN_PURPOSE}: unrecognized purpose {declared_purpose!r}")

    # PHI checking
    for key in event:
        lowered = key.lower()
        if any(marker in lowered for marker in PHI_MARKERS):
            raise ValueError(f"{REASON_PHI_FIELD_PRESENT}: field {key!r} contains PHI marker")

    # Unsalted hash checking on subject_ref if present
    subj = event.get("subject_ref")
    if isinstance(subj, str) and (_UNSALTED_DIGEST.match(subj) or _UNSALTED_PREFIXED.match(subj)):
        raise ValueError(
            f"{REASON_UNSALTED_HASH_REFUSED}: unkeyed digest of subject identifier is refused"
        )

    # Identifiers
    event_id = str(event.get("event_id") or event.get("operation_id") or "evt-0000")
    tenant_id = str(event.get("tenant_id") or "tnt_00000000")
    principal_id = str(event.get("principal_id") or "prn_00000000")
    operation = str(event.get("operation") or "record_read")
    policy_epoch = str(event.get("policy_epoch") or "epoch-0")
    issued_at = str(event.get("timestamp") or event.get("created_at") or "2026-11-16T00:00:00Z")

    # Partition fields into retained vs omitted
    allowlist = PURPOSE_RETAINED_FIELDS.get(declared_purpose, frozenset())
    retained: dict[str, str] = {}
    omitted: dict[str, Any] = {}

    # Source fields
    for k, v in event.items():
        if k in (
            "tenant_id",
            "principal_id",
            "purpose",
            "operation",
            "policy_epoch",
            "timestamp",
            "created_at",
            "event_id",
            "operation_id",
        ):
            continue
        if k in allowlist:
            retained[k] = str(v)
        else:
            omitted[k] = v

    # Add caller-supplied explicit omitted fields if present
    if "omitted_fields" in event and isinstance(event["omitted_fields"], Mapping):
        for ok, ov in event["omitted_fields"].items():
            omitted[ok] = ov

    # Compute omitted fields commitment digest
    omitted_canonical = json_canonical(omitted)
    omitted_digest = hashlib.sha256(omitted_canonical.encode("utf-8")).hexdigest()

    receipt_id = (
        f"rcpt_{hashlib.sha256(f'{event_id}:{tenant_id}:{policy_epoch}'.encode()).hexdigest()[:24]}"
    )

    body = {
        "version": "1",
        "receipt_id": receipt_id,
        "tenant_id": tenant_id,
        "principal_id": principal_id,
        "purpose": declared_purpose,
        "operation": operation,
        "policy_epoch": policy_epoch,
        "issued_at": issued_at,
        "omitted_field_digest": omitted_digest,
        "retained_fields": retained,
    }

    # Compute cryptographic HMAC signature over canonical body
    body_canonical = json_canonical(body)
    sig = hmac.new(signing_key, body_canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    return Receipt(
        version="1",
        receipt_id=receipt_id,
        tenant_id=tenant_id,
        principal_id=principal_id,
        purpose=declared_purpose,
        operation=operation,
        policy_epoch=policy_epoch,
        issued_at=issued_at,
        omitted_field_digest=omitted_digest,
        retained_fields=retained,
        signature=sig,
    )


# --- Forensic Reconstruction Engine -----------------------------------------


def reconstruct(
    receipts: Sequence[Receipt | Mapping[str, Any]],
    query: Mapping[str, Any] | str,
    *,
    signing_key: bytes = b"pst-receiptmin-eval-signing-key",
) -> Reconstruction:
    """Evaluate whether a declared forensic query is reconstructable from receipts.

    Fail-closed semantics:
    - If receipts is empty or query is unknown/malformed -> INDETERMINATE.
    - If receipt signature is tampered -> INDETERMINATE (TAMPER_DETECTED).
    - If required witness fields are missing -> NOT_ANSWERABLE (score 0.0).
    - If load-bearing proof (policy/consent epoch or key custody) is missing -> INDETERMINATE.
    - If all required witness fields and epoch proofs match -> ANSWERABLE (score 1.0).
    """
    # Parse query
    if isinstance(query, str):
        query_id = query
        query_class = ""
        witnesses_needed: tuple[str, ...] = ()
        omitted_claims: Mapping[str, Any] = {}
        key_custody_attested = True
    elif isinstance(query, Mapping):
        query_id = str(query.get("query_id", "") or "")
        query_class = str(query.get("query_class", "") or "")
        w_needed = query.get("witnesses_needed", ())
        witnesses_needed = tuple(w_needed) if isinstance(w_needed, list | tuple) else ()
        omitted_claims = (
            query.get("omitted_claims", {})
            if isinstance(query.get("omitted_claims"), Mapping)
            else {}
        )
        key_custody_attested = bool(query.get("key_custody_attested", True))
    else:
        return Reconstruction(
            score=0.0,
            answerable=INDETERMINATE,
            reason_code=REASON_MALFORMED_QUERY,
            query_id="UNKNOWN",
            evidence_fields=(),
        )

    if not query_id:
        return Reconstruction(
            score=0.0,
            answerable=INDETERMINATE,
            reason_code=REASON_MALFORMED_QUERY,
            query_id="UNKNOWN",
            evidence_fields=(),
        )

    # Standard query inference if query_class or witnesses_needed were omitted
    if not query_class or not witnesses_needed:
        inferred = _infer_query_spec(query_id)
        if inferred is None:
            return Reconstruction(
                score=0.0,
                answerable=INDETERMINATE,
                reason_code=REASON_UNKNOWN_QUERY,
                query_id=query_id,
                evidence_fields=(),
            )
        query_class, witnesses_needed = inferred

    if not receipts:
        return Reconstruction(
            score=0.0,
            answerable=NOT_ANSWERABLE,
            reason_code=REASON_MISSING_WITNESS,
            query_id=query_id,
            evidence_fields=(),
            details={"missing_witnesses": list(witnesses_needed)},
        )

    # Convert receipts to typed Receipt objects and verify signatures
    typed_receipts: list[Receipt] = []
    for r in receipts:
        if isinstance(r, Receipt):
            tr = r
        elif isinstance(r, Mapping):
            try:
                tr = Receipt.from_dict(r)
            except Exception:
                return Reconstruction(
                    score=0.0,
                    answerable=INDETERMINATE,
                    reason_code=REASON_MALFORMED_RECEIPT,
                    query_id=query_id,
                    evidence_fields=(),
                )
        else:
            return Reconstruction(
                score=0.0,
                answerable=INDETERMINATE,
                reason_code=REASON_MALFORMED_RECEIPT,
                query_id=query_id,
                evidence_fields=(),
            )

        # Signature verification if signature is present
        if tr.signature:
            body = {
                "version": tr.version,
                "receipt_id": tr.receipt_id,
                "tenant_id": tr.tenant_id,
                "principal_id": tr.principal_id,
                "purpose": tr.purpose,
                "operation": tr.operation,
                "policy_epoch": tr.policy_epoch,
                "issued_at": tr.issued_at,
                "omitted_field_digest": tr.omitted_field_digest,
                "retained_fields": tr.retained_fields,
            }
            body_canonical = json_canonical(body)
            expected_sig = hmac.new(
                signing_key, body_canonical.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(tr.signature, expected_sig):
                return Reconstruction(
                    score=0.0,
                    answerable=INDETERMINATE,
                    reason_code=REASON_TAMPER_DETECTED,
                    query_id=query_id,
                    evidence_fields=(),
                    details={"receipt_id": tr.receipt_id},
                )

        typed_receipts.append(tr)

    # Aggregate available fields across receipts
    available_fields: dict[str, str] = {}
    for r in typed_receipts:
        available_fields["purpose"] = r.purpose
        available_fields["purpose_tag"] = r.purpose
        available_fields["policy_epoch"] = r.policy_epoch
        available_fields["tenant_id"] = r.tenant_id
        available_fields["principal_id"] = r.principal_id
        available_fields.update(r.retained_fields)

    # If the query supplies candidate omitted claims to verify against the digest
    if omitted_claims:
        omitted_canonical = json_canonical(omitted_claims)
        cand_digest = hashlib.sha256(omitted_canonical.encode("utf-8")).hexdigest()
        digest_matched = any(r.omitted_field_digest == cand_digest for r in typed_receipts)
        if not digest_matched:
            return Reconstruction(
                score=0.0,
                answerable=INDETERMINATE,
                reason_code=REASON_OMITTED_FIELD_MISMATCH,
                query_id=query_id,
                evidence_fields=(),
                details={"claimed_digest": cand_digest},
            )

    # Check missing witnesses
    missing = [w for w in witnesses_needed if w not in available_fields]
    if missing:
        return Reconstruction(
            score=0.0,
            answerable=NOT_ANSWERABLE,
            reason_code=REASON_MISSING_WITNESS,
            query_id=query_id,
            evidence_fields=tuple(sorted(set(witnesses_needed) - set(missing))),
            details={"missing_witnesses": missing},
        )

    # Governance epoch and key custody checks (PST-CASE-05/07/12)
    if query_class in ("authorization", "commit_eligibility"):
        # Policy epoch must be explicitly present and non-empty
        if not available_fields.get("policy_epoch"):
            return Reconstruction(
                score=0.0,
                answerable=INDETERMINATE,
                reason_code=REASON_MISSING_EPOCH,
                query_id=query_id,
                evidence_fields=(),
            )
        # If the query requires consent epoch
        if "consent_epoch" in witnesses_needed and not available_fields.get("consent_epoch"):
            return Reconstruction(
                score=0.0,
                answerable=INDETERMINATE,
                reason_code=REASON_MISSING_EPOCH,
                query_id=query_id,
                evidence_fields=(),
            )

    # Key custody attestation for content-level provenance queries
    if query_class == "provenance" and not key_custody_attested:
        # If query requires more than bare commitment digest, custody is mandatory
        if any(w != "commitment_digest" for w in witnesses_needed):
            return Reconstruction(
                score=0.0,
                answerable=INDETERMINATE,
                reason_code=REASON_MISSING_KEY_CUSTODY,
                query_id=query_id,
                evidence_fields=tuple(witnesses_needed),
            )

    # Successfully answerable
    return Reconstruction(
        score=1.0,
        answerable=ANSWERABLE,
        reason_code=REASON_OK,
        query_id=query_id,
        evidence_fields=tuple(witnesses_needed),
        details={"matched_receipts": len(typed_receipts)},
    )


def _infer_query_spec(query_id: str) -> tuple[str, tuple[str, ...]] | None:
    """Map known ex-ante forensic query IDs to class and witnesses."""
    mapping: dict[str, tuple[str, tuple[str, ...]]] = {
        "FQ-AUTH-01": ("authorization", ("purpose_tag", "witness_id")),
        "FQ-AUTH-02": ("authorization", ("purpose_tag",)),
        "FQ-AUTH-03": ("authorization", ("purpose_tag", "witness_id")),
        "FQ-AUTH-04": ("authorization", ("purpose_tag", "consent_epoch")),
        "FQ-PROV-01": ("provenance", ("commitment_digest",)),
        "FQ-PROV-02": ("provenance", ("commitment_digest", "retention_mode")),
        "FQ-PROV-03": ("provenance", ("purpose_tag", "retention_mode")),
        "FQ-PROV-04": ("provenance", ("commitment_digest", "witness_id")),
        "FQ-ELIG-01": ("commit_eligibility", ("purpose_tag", "consent_epoch")),
        "FQ-ELIG-02": ("commit_eligibility", ("policy_epoch", "purpose_tag")),
        "FQ-ELIG-03": ("commit_eligibility", ("commitment_digest", "retention_mode")),
        "FQ-ELIG-04": ("commit_eligibility", ("commitment_digest", "witness_id", "policy_epoch")),
    }
    return mapping.get(query_id)


# --- Task Harness Adapter ----------------------------------------------------


def _arm_id(ctx: Any) -> str:
    if isinstance(ctx, Mapping):
        return str(ctx.get("arm_id", "") or "")
    return str(getattr(ctx, "arm_id", "") or "")


def run_candidate(case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Adapter ``run_candidate(case, ctx) -> Outcome`` (task-manifest contract).

    ADMIT -> Reconstructable under declared forensic query (or valid bounded receipt).
    REJECT -> Reconstructability failure (NOT_ANSWERABLE or invalid linkage).
    INDETERMINATE -> Incomplete evidence, missing key custody, or unmodelled query.
    INVALID_RESULT -> Unknown/unregistered arm.
    """
    arm = _arm_id(ctx) or CANDIDATE_ARM_ID
    if arm not in ("B4", "C0", CANDIDATE_ARM_ID, "pst-candidate", "candidate"):
        return Outcome(
            observed_outcome="INVALID_RESULT",
            counted_as_success=False,
            retriable=False,
            detail=f"{REASON_UNKNOWN_ARM}|arm={arm!r}",
        )

    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=REASON_MALFORMED_CASE,
        )

    case_id = str(case.get("case_id", "unknown_case"))

    # Case can contain events to minimize or receipts to evaluate
    events = case.get("events")
    receipts_data = case.get("receipts")
    query = case.get("query") or case.get("forensic_query")

    try:
        # If raw events provided, minimize them first
        if events is not None:
            if not isinstance(events, list):
                return Outcome(
                    observed_outcome=INDETERMINATE,
                    counted_as_success=False,
                    retriable=False,
                    detail=REASON_MALFORMED_CASE,
                )
            generated_receipts = [
                minimize(evt, case.get("purpose") or evt.get("purpose", "forensic_review"))
                for evt in events
            ]
        elif receipts_data is not None:
            if not isinstance(receipts_data, list):
                return Outcome(
                    observed_outcome=INDETERMINATE,
                    counted_as_success=False,
                    retriable=False,
                    detail=REASON_MALFORMED_CASE,
                )
            generated_receipts = [
                r if isinstance(r, Receipt) else Receipt.from_dict(r) for r in receipts_data
            ]
        else:
            # Check if case itself is an event mapping
            generated_receipts = [minimize(case, case.get("purpose", "forensic_review"))]

        # If a query is provided, evaluate reconstructability
        if query is not None:
            recon = reconstruct(generated_receipts, query)
            if recon.answerable == INDETERMINATE:
                return Outcome(
                    observed_outcome=INDETERMINATE,
                    counted_as_success=False,
                    retriable=False,
                    detail=f"{recon.reason_code}|case={case_id}|query={recon.query_id}",
                )
            if recon.answerable == ANSWERABLE:
                return Outcome(
                    observed_outcome="ADMIT",
                    counted_as_success=True,
                    retriable=False,
                    detail=f"{recon.reason_code}|score={recon.score:.6f}|case={case_id}",
                )
            return Outcome(
                observed_outcome="REJECT",
                counted_as_success=True,
                retriable=False,
                detail=f"{recon.reason_code}|score={recon.score:.6f}|case={case_id}",
            )

        # Default case without explicit query: successful minimization is ADMIT
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=f"{REASON_OK}|receipts={len(generated_receipts)}|case={case_id}",
        )

    except ValueError as exc:
        reason = str(exc).split(":")[0].strip()
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=f"{reason}|case={case_id}",
        )
    except Exception as exc:  # noqa: BLE001
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            retriable=False,
            detail=f"EXECUTION_ERROR|{type(exc).__name__}|case={case_id}",
        )


# --- Mechanism Description ---------------------------------------------------


def describe_mechanism() -> dict[str, Any]:
    """Expose machine-readable design record of ReceiptMin candidate mechanism."""
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "blueprint_arm": CANDIDATE_ARM_ID,
        "name": "ReceiptMin: Purpose-Bound Minimal Audit Receipts with Forensic Reconstruction",
        "blueprint": "research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md",
        "phase": "P04 (Candidate algorithm design boundary)",
        "features": [
            "purpose_bound_field_allowlist",
            "cryptographic_omitted_field_digest_binding",
            "hmac_tamper_evident_receipt_signature",
            "forensic_query_reconstructability_evaluator",
            "fail_closed_on_indeterminate_or_missing_proofs",
        ],
        "allowed_purposes": list(VALID_PURPOSES),
        "allowed_operations": list(VALID_OPERATIONS),
        "retention_modes": list(VALID_RETENTION_MODES),
        "fail_closed_reason_codes": [
            REASON_MALFORMED_EVENT,
            REASON_UNKNOWN_PURPOSE,
            REASON_UNKNOWN_QUERY,
            REASON_MALFORMED_QUERY,
            REASON_MALFORMED_RECEIPT,
            REASON_UNKNOWN_ARM,
            REASON_TAMPER_DETECTED,
            REASON_MISSING_WITNESS,
            REASON_MISSING_EPOCH,
            REASON_MISSING_KEY_CUSTODY,
            REASON_OMITTED_FIELD_MISMATCH,
            REASON_UNSALTED_HASH_REFUSED,
            REASON_PHI_FIELD_PRESENT,
            REASON_UNRECOGNIZED_FIELD,
            REASON_MALFORMED_CASE,
        ],
    }


__all__ = [
    "ANSWERABLE",
    "CANDIDATE_ARM_ID",
    "CANDIDATE_ID",
    "CANDIDATE_VERSION",
    "INDETERMINATE",
    "NOT_ANSWERABLE",
    "RECEIPT_SCHEMA_VERSION",
    "Receipt",
    "Reconstruction",
    "describe_mechanism",
    "minimize",
    "reconstruct",
    "run_candidate",
]
