"""DSN-X01_state_spec — 3-way durable state machine for recoverable outcomes.

Purpose
-------
Reference semantics for the DSN 2027 study "Recoverable Safety Journals for
Crash-Consistent AI-Mediated Health-State Mutations" (RQ1). A clinical write
intent is durable only when the *joint* state of three independent channels
agrees: the committed clinical row, the immutable decision receipt (ledger)
and the transactional outbox record with its partial-effect delivery receipts.
:func:`evaluate_durability` maps one ``(write_intent, durable_state)`` pair to
exactly one verdict:

- ``COMMITTED`` — every channel carries matching, well-formed evidence for the
  operation. Durable success is NEVER inferred from an HTTP response or ACK;
  it requires a decision receipt bound to the committed clinical row.
- ``REJECTED`` — positive durable evidence that the operation did not (and
  must not) count as committed: no durable write evidence anywhere (crash
  before WAL), consent revoked before the commit, a durable outbox failure
  record, or a clinical row stamped with a post-revocation consent epoch.
- ``INDETERMINATE`` — torn, stale, orphaned, tampered or contradictory
  evidence. This is the fail-closed default: a missing, stale or corrupt
  receipt never becomes a positive outcome, and disagreeing channels are
  never coerced into a "safe rejection".

Allowed input
-------------
Typed, JSON-serializable dataclasses: :class:`WriteIntent`,
:class:`DurableState` and their channel records (``from_dict`` constructors
are provided; structural errors raise ``ValueError`` at construction). All
timestamps are logical integers supplied by the caller — no hidden clock, no
randomness, no I/O, no provider calls. The function is pure: identical inputs
always yield an equal verdict, so retries keyed by the stable operation ID
re-evaluate idempotently.

Failure semantics
-----------------
Semantically invalid evidence never raises: every failure mode maps to a
stable ``reason_code`` on :class:`DurabilityVerdict` (malformed inputs,
channel disagreement, digest tampering, timestamp anomalies). Evaluation is
additionally wrapped in a fail-closed guard — an unexpected internal error
yields ``INDETERMINATE`` / ``INTERNAL_EVALUATION_ERROR``, never a silent
acceptance or rejection. :func:`recover` folds an :class:`EventHistory`
(write intents, post-crash durable snapshots, crash markers, recorded
evaluations) into one :class:`RecoveryVerdict`; incomplete, malformed or
conflicting histories fail closed.

Version
-------
``STATE_MACHINE_VERSION = "clara.dsn.state-machine-v1"`` (additive-only
evolution within v1; the verdict shape is version-pinned for the oracle).
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

STATE_MACHINE_VERSION: Final[str] = "clara.dsn.state-machine-v1"

RECEIPT_DECISION_ACCEPT: Final[str] = "ACCEPT"


class DurabilityOutcome(enum.StrEnum):
    """Three-way recoverable outcome assigned to every evaluated state."""

    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    INDETERMINATE = "INDETERMINATE"


class ChannelStatus(enum.StrEnum):
    """Durable status of one evidence channel.

    ABSENT — no durable record. PRESENT — durable, well-formed record.
    CORRUPT — record exists but its integrity check failed (tamper / torn
    write). FAILED — durable failure record exists (e.g. fsync error).
    """

    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    CORRUPT = "CORRUPT"
    FAILED = "FAILED"


REASON_COMMITTED_ALL_CHANNELS_AGREE: Final[str] = "COMMITTED_ALL_CHANNELS_AGREE"
REASON_COMMITTED_PRE_REVOCATION: Final[str] = "COMMITTED_PRE_REVOCATION"
REASON_COMMITTED_PENDING_DELIVERY: Final[str] = "COMMITTED_PENDING_DELIVERY"
REASON_COMMITTED_EFFECT_APPLIED: Final[str] = "COMMITTED_EFFECT_APPLIED"
REASON_COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT: Final[str] = (
    "COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT"
)
REASON_NOT_COMMITTED_NO_DURABLE_EVIDENCE: Final[str] = "NOT_COMMITTED_NO_DURABLE_EVIDENCE"
REASON_CONSENT_REVOKED_BEFORE_COMMIT: Final[str] = "CONSENT_REVOKED_BEFORE_COMMIT"
REASON_FORBIDDEN_WRITE_POST_REVOCATION: Final[str] = "FORBIDDEN_WRITE_POST_REVOCATION"
REASON_OUTBOX_FSYNC_FAILED: Final[str] = "OUTBOX_FSYNC_FAILED"
REASON_MALFORMED_WRITE_INTENT: Final[str] = "MALFORMED_WRITE_INTENT"
REASON_MALFORMED_DURABLE_STATE: Final[str] = "MALFORMED_DURABLE_STATE"
REASON_STATE_OPERATION_MISMATCH: Final[str] = "STATE_OPERATION_MISMATCH"
REASON_CLINICAL_ROW_CORRUPT: Final[str] = "CLINICAL_ROW_CORRUPT"
REASON_DECISION_RECEIPT_CORRUPT: Final[str] = "DECISION_RECEIPT_CORRUPT"
REASON_CONSENT_EPOCH_ANOMALY: Final[str] = "CONSENT_EPOCH_ANOMALY"
REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW: Final[str] = "ORPHAN_RECEIPT_NO_CLINICAL_ROW"
REASON_OUTBOX_ORPHAN_NO_CLINICAL_ROW: Final[str] = "OUTBOX_ORPHAN_NO_CLINICAL_ROW"
REASON_RECEIPT_DIGEST_MISMATCH: Final[str] = "RECEIPT_DIGEST_MISMATCH"
REASON_MISSING_DECISION_RECEIPT: Final[str] = "MISSING_DECISION_RECEIPT"
REASON_STALE_RECEIPT_VERSION_MISMATCH: Final[str] = "STALE_RECEIPT_VERSION_MISMATCH"
REASON_RECEIPT_EPOCH_MISMATCH: Final[str] = "RECEIPT_EPOCH_MISMATCH"
REASON_RECEIPT_DECISION_CONFLICT: Final[str] = "RECEIPT_DECISION_CONFLICT"
REASON_RECEIPT_TIMESTAMP_ANOMALY: Final[str] = "RECEIPT_TIMESTAMP_ANOMALY"
REASON_WAL_COMMIT_TIMESTAMP_ANOMALY: Final[str] = "WAL_COMMIT_TIMESTAMP_ANOMALY"
REASON_OUTBOX_TIMESTAMP_ANOMALY: Final[str] = "OUTBOX_TIMESTAMP_ANOMALY"
REASON_DELIVERY_TIMESTAMP_ANOMALY: Final[str] = "DELIVERY_TIMESTAMP_ANOMALY"
REASON_DUPLICATE_EFFECT_DIVERGENCE: Final[str] = "DUPLICATE_EFFECT_DIVERGENCE"
REASON_OUTBOX_RECORD_MISSING: Final[str] = "OUTBOX_RECORD_MISSING"
REASON_INTERNAL_EVALUATION_ERROR: Final[str] = "INTERNAL_EVALUATION_ERROR"
REASON_HISTORY_INCOMPLETE: Final[str] = "HISTORY_INCOMPLETE"
REASON_MALFORMED_HISTORY_EVENT: Final[str] = "MALFORMED_HISTORY_EVENT"
REASON_UNKNOWN_HISTORY_EVENT: Final[str] = "UNKNOWN_HISTORY_EVENT"
REASON_HISTORY_INTENT_CONFLICT: Final[str] = "HISTORY_INTENT_CONFLICT"

REASON_CODES: Final[tuple[str, ...]] = (
    REASON_COMMITTED_ALL_CHANNELS_AGREE,
    REASON_COMMITTED_PRE_REVOCATION,
    REASON_COMMITTED_PENDING_DELIVERY,
    REASON_COMMITTED_EFFECT_APPLIED,
    REASON_COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT,
    REASON_NOT_COMMITTED_NO_DURABLE_EVIDENCE,
    REASON_CONSENT_REVOKED_BEFORE_COMMIT,
    REASON_FORBIDDEN_WRITE_POST_REVOCATION,
    REASON_OUTBOX_FSYNC_FAILED,
    REASON_MALFORMED_WRITE_INTENT,
    REASON_MALFORMED_DURABLE_STATE,
    REASON_STATE_OPERATION_MISMATCH,
    REASON_CLINICAL_ROW_CORRUPT,
    REASON_DECISION_RECEIPT_CORRUPT,
    REASON_CONSENT_EPOCH_ANOMALY,
    REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW,
    REASON_OUTBOX_ORPHAN_NO_CLINICAL_ROW,
    REASON_RECEIPT_DIGEST_MISMATCH,
    REASON_MISSING_DECISION_RECEIPT,
    REASON_STALE_RECEIPT_VERSION_MISMATCH,
    REASON_RECEIPT_EPOCH_MISMATCH,
    REASON_RECEIPT_DECISION_CONFLICT,
    REASON_RECEIPT_TIMESTAMP_ANOMALY,
    REASON_WAL_COMMIT_TIMESTAMP_ANOMALY,
    REASON_OUTBOX_TIMESTAMP_ANOMALY,
    REASON_DELIVERY_TIMESTAMP_ANOMALY,
    REASON_DUPLICATE_EFFECT_DIVERGENCE,
    REASON_OUTBOX_RECORD_MISSING,
    REASON_INTERNAL_EVALUATION_ERROR,
    REASON_HISTORY_INCOMPLETE,
    REASON_MALFORMED_HISTORY_EVENT,
    REASON_UNKNOWN_HISTORY_EVENT,
    REASON_HISTORY_INTENT_CONFLICT,
)

_OP_ID_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._:@/-]{1,128}")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")


def _valid_op_id(value: Any) -> bool:
    return isinstance(value, str) and _OP_ID_RE.fullmatch(value) is not None


def _valid_label(value: Any) -> bool:
    return isinstance(value, str) and _OP_ID_RE.fullmatch(value) is not None


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _valid_int(value: Any, *, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _synthetic_digest(label: str) -> str:
    """Deterministic synthetic digest for spec fixtures (never real data)."""

    return _sha256_text("clara.dsn.synthetic:" + label)


@dataclasses.dataclass(frozen=True)
class WriteIntent:
    """Governed write intent (the operation whose durability is adjudicated).

    ``authorized_consent_epoch`` is the consent/policy epoch the principal was
    authorized under; ``payload_digest_sha256`` binds the intent to its
    clinical payload without carrying any patient-identifying content.
    """

    operation_id: str
    tenant_id: str
    principal_id: str
    purpose: str
    authorized_consent_epoch: int
    payload_digest_sha256: str
    issued_logical_time: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "purpose": self.purpose,
            "authorized_consent_epoch": self.authorized_consent_epoch,
            "payload_digest_sha256": self.payload_digest_sha256,
            "issued_logical_time": self.issued_logical_time,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WriteIntent:
        try:
            return cls(
                operation_id=payload["operation_id"],
                tenant_id=payload["tenant_id"],
                principal_id=payload["principal_id"],
                purpose=payload["purpose"],
                authorized_consent_epoch=payload["authorized_consent_epoch"],
                payload_digest_sha256=payload["payload_digest_sha256"],
                issued_logical_time=payload["issued_logical_time"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed WriteIntent payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class ClinicalRowState:
    """Committed clinical row channel (the WAL-backed mutation itself)."""

    status: ChannelStatus
    operation_id: str | None = None
    row_version: int | None = None
    wal_commit_logical_time: int | None = None
    consent_epoch_at_commit: int | None = None
    row_digest_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "operation_id": self.operation_id,
            "row_version": self.row_version,
            "wal_commit_logical_time": self.wal_commit_logical_time,
            "consent_epoch_at_commit": self.consent_epoch_at_commit,
            "row_digest_sha256": self.row_digest_sha256,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ClinicalRowState:
        try:
            return cls(
                status=ChannelStatus(payload["status"]),
                operation_id=payload.get("operation_id"),
                row_version=payload.get("row_version"),
                wal_commit_logical_time=payload.get("wal_commit_logical_time"),
                consent_epoch_at_commit=payload.get("consent_epoch_at_commit"),
                row_digest_sha256=payload.get("row_digest_sha256"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed ClinicalRowState payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class DecisionReceipt:
    """Versioned decision receipt (immutable decision lineage / ledger).

    ``stored_transition_digest`` is the digest of the clinical transition the
    receipt signs; when present it must equal the committed row digest, and a
    mismatch is forensic tamper evidence (CASE_MATRIX DSN-CASE-06).
    """

    status: ChannelStatus
    operation_id: str | None = None
    row_version: int | None = None
    consent_epoch: int | None = None
    decision: str | None = None
    receipt_logical_time: int | None = None
    receipt_digest_sha256: str | None = None
    stored_transition_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "operation_id": self.operation_id,
            "row_version": self.row_version,
            "consent_epoch": self.consent_epoch,
            "decision": self.decision,
            "receipt_logical_time": self.receipt_logical_time,
            "receipt_digest_sha256": self.receipt_digest_sha256,
            "stored_transition_digest": self.stored_transition_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DecisionReceipt:
        try:
            return cls(
                status=ChannelStatus(payload["status"]),
                operation_id=payload.get("operation_id"),
                row_version=payload.get("row_version"),
                consent_epoch=payload.get("consent_epoch"),
                decision=payload.get("decision"),
                receipt_logical_time=payload.get("receipt_logical_time"),
                receipt_digest_sha256=payload.get("receipt_digest_sha256"),
                stored_transition_digest=payload.get("stored_transition_digest"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed DecisionReceipt payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class DeliveryReceipt:
    """Partial-effect receipt for one outbox delivery attempt."""

    operation_id: str
    attempt: int
    effect_applied: bool
    delivered_logical_time: int
    effect_receipt_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "attempt": self.attempt,
            "effect_applied": self.effect_applied,
            "delivered_logical_time": self.delivered_logical_time,
            "effect_receipt_digest": self.effect_receipt_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DeliveryReceipt:
        try:
            return cls(
                operation_id=payload["operation_id"],
                attempt=payload["attempt"],
                effect_applied=payload["effect_applied"],
                delivered_logical_time=payload["delivered_logical_time"],
                effect_receipt_digest=payload.get("effect_receipt_digest"),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed DeliveryReceipt payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class OutboxState:
    """Transactional outbox channel with its partial-effect delivery receipts."""

    status: ChannelStatus
    operation_id: str | None = None
    recorded_logical_time: int | None = None
    deliveries: tuple[DeliveryReceipt, ...] = ()
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "operation_id": self.operation_id,
            "recorded_logical_time": self.recorded_logical_time,
            "deliveries": [d.to_dict() for d in self.deliveries],
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OutboxState:
        try:
            return cls(
                status=ChannelStatus(payload["status"]),
                operation_id=payload.get("operation_id"),
                recorded_logical_time=payload.get("recorded_logical_time"),
                deliveries=tuple(
                    DeliveryReceipt.from_dict(d) for d in payload.get("deliveries", ())
                ),
                failure_reason=payload.get("failure_reason"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed OutboxState payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class DurableState:
    """Post-crash durable snapshot of the three evidence channels.

    ``current_consent_epoch`` is the governance epoch observed at recovery
    time; ``reconciler_logical_time`` bounds admissible durable timestamps.
    """

    clinical_row: ClinicalRowState
    decision_receipt: DecisionReceipt
    outbox: OutboxState
    current_consent_epoch: int
    reconciler_logical_time: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "clinical_row": self.clinical_row.to_dict(),
            "decision_receipt": self.decision_receipt.to_dict(),
            "outbox": self.outbox.to_dict(),
            "current_consent_epoch": self.current_consent_epoch,
            "reconciler_logical_time": self.reconciler_logical_time,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DurableState:
        try:
            return cls(
                clinical_row=ClinicalRowState.from_dict(payload["clinical_row"]),
                decision_receipt=DecisionReceipt.from_dict(payload["decision_receipt"]),
                outbox=OutboxState.from_dict(payload["outbox"]),
                current_consent_epoch=payload["current_consent_epoch"],
                reconciler_logical_time=payload["reconciler_logical_time"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed DurableState payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class DurabilityVerdict:
    """Exactly one outcome plus a stable reason code (JSON-serializable)."""

    outcome: DurabilityOutcome
    reason_code: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DurabilityVerdict:
        try:
            return cls(
                outcome=DurabilityOutcome(payload["outcome"]),
                reason_code=payload["reason_code"],
                details=dict(payload.get("details", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed DurabilityVerdict payload: {exc}") from exc


def _intent_issues(intent: WriteIntent) -> list[str]:
    issues: list[str] = []
    if not _valid_op_id(intent.operation_id):
        issues.append("operation_id")
    if not _valid_label(intent.tenant_id):
        issues.append("tenant_id")
    if not _valid_label(intent.principal_id):
        issues.append("principal_id")
    if not _valid_label(intent.purpose):
        issues.append("purpose")
    if not _valid_int(intent.authorized_consent_epoch):
        issues.append("authorized_consent_epoch")
    if not _valid_sha256(intent.payload_digest_sha256):
        issues.append("payload_digest_sha256")
    if not _valid_int(intent.issued_logical_time):
        issues.append("issued_logical_time")
    return issues


def _delivery_issues(delivery: DeliveryReceipt) -> list[str]:
    issues: list[str] = []
    if not _valid_op_id(delivery.operation_id):
        issues.append("delivery.operation_id")
    if not _valid_int(delivery.attempt, minimum=1):
        issues.append("delivery.attempt")
    if not isinstance(delivery.effect_applied, bool):
        issues.append("delivery.effect_applied")
    if not _valid_int(delivery.delivered_logical_time):
        issues.append("delivery.delivered_logical_time")
    if delivery.effect_applied and not _valid_sha256(delivery.effect_receipt_digest):
        issues.append("delivery.effect_receipt_digest")
    return issues


def _state_issues(state: DurableState) -> list[str]:
    """Structural validation; returns the list of offending field names."""

    issues: list[str] = []
    if not _valid_int(state.current_consent_epoch):
        issues.append("current_consent_epoch")
    if not _valid_int(state.reconciler_logical_time):
        issues.append("reconciler_logical_time")

    row = state.clinical_row
    if not isinstance(row.status, ChannelStatus):
        issues.append("clinical_row.status")
    elif row.status is ChannelStatus.ABSENT:
        if any(
            v is not None
            for v in (
                row.operation_id,
                row.row_version,
                row.wal_commit_logical_time,
                row.consent_epoch_at_commit,
                row.row_digest_sha256,
            )
        ):
            issues.append("clinical_row.absent_carries_payload")
    elif row.status is ChannelStatus.PRESENT:
        if not _valid_op_id(row.operation_id):
            issues.append("clinical_row.operation_id")
        if not _valid_int(row.row_version):
            issues.append("clinical_row.row_version")
        if not _valid_int(row.wal_commit_logical_time):
            issues.append("clinical_row.wal_commit_logical_time")
        if not _valid_int(row.consent_epoch_at_commit):
            issues.append("clinical_row.consent_epoch_at_commit")
        if not _valid_sha256(row.row_digest_sha256):
            issues.append("clinical_row.row_digest_sha256")
    elif row.status is ChannelStatus.CORRUPT:
        if not _valid_op_id(row.operation_id):
            issues.append("clinical_row.operation_id")

    receipt = state.decision_receipt
    if not isinstance(receipt.status, ChannelStatus):
        issues.append("decision_receipt.status")
    elif receipt.status is ChannelStatus.ABSENT:
        if any(
            v is not None
            for v in (
                receipt.operation_id,
                receipt.row_version,
                receipt.consent_epoch,
                receipt.decision,
                receipt.receipt_logical_time,
                receipt.receipt_digest_sha256,
                receipt.stored_transition_digest,
            )
        ):
            issues.append("decision_receipt.absent_carries_payload")
    elif receipt.status is ChannelStatus.PRESENT:
        if not _valid_op_id(receipt.operation_id):
            issues.append("decision_receipt.operation_id")
        if not _valid_int(receipt.row_version):
            issues.append("decision_receipt.row_version")
        if not _valid_int(receipt.consent_epoch):
            issues.append("decision_receipt.consent_epoch")
        if not _valid_label(receipt.decision):
            issues.append("decision_receipt.decision")
        if not _valid_int(receipt.receipt_logical_time):
            issues.append("decision_receipt.receipt_logical_time")
        if not _valid_sha256(receipt.receipt_digest_sha256):
            issues.append("decision_receipt.receipt_digest_sha256")
        if receipt.stored_transition_digest is not None and not _valid_sha256(
            receipt.stored_transition_digest
        ):
            issues.append("decision_receipt.stored_transition_digest")
    elif receipt.status is ChannelStatus.CORRUPT:
        if not _valid_op_id(receipt.operation_id):
            issues.append("decision_receipt.operation_id")

    outbox = state.outbox
    if not isinstance(outbox.status, ChannelStatus):
        issues.append("outbox.status")
    else:
        if outbox.status is ChannelStatus.ABSENT:
            if outbox.operation_id is not None or outbox.deliveries:
                issues.append("outbox.absent_carries_payload")
        elif not _valid_op_id(outbox.operation_id):
            issues.append("outbox.operation_id")
        if outbox.status is ChannelStatus.PRESENT:
            if not _valid_int(outbox.recorded_logical_time):
                issues.append("outbox.recorded_logical_time")
        if outbox.status is ChannelStatus.FAILED and not _valid_label(outbox.failure_reason):
            issues.append("outbox.failure_reason")
        for delivery in outbox.deliveries:
            issues.extend(_delivery_issues(delivery))
    return issues


def _indeterminate(reason_code: str, **details: Any) -> DurabilityVerdict:
    return DurabilityVerdict(
        outcome=DurabilityOutcome.INDETERMINATE, reason_code=reason_code, details=dict(details)
    )


def _evaluate_channels(
    intent: WriteIntent, state: DurableState
) -> DurabilityVerdict:
    """Core reconciliation of the three channels (pure, fail-closed)."""

    row = state.clinical_row
    receipt = state.decision_receipt
    outbox = state.outbox
    op_id = intent.operation_id

    # 1. Governance race (CASE DSN-CASE-05): consent revoked before commit.
    if row.status is ChannelStatus.PRESENT:
        epoch_at_commit = row.consent_epoch_at_commit or 0
        if epoch_at_commit > intent.authorized_consent_epoch:
            return DurabilityVerdict(
                outcome=DurabilityOutcome.REJECTED,
                reason_code=REASON_FORBIDDEN_WRITE_POST_REVOCATION,
                details={
                    "authorized_consent_epoch": intent.authorized_consent_epoch,
                    "consent_epoch_at_commit": epoch_at_commit,
                },
            )

    # 2. Durable outbox failure record: the side effect can never be delivered.
    if outbox.status is ChannelStatus.FAILED:
        return DurabilityVerdict(
            outcome=DurabilityOutcome.REJECTED,
            reason_code=REASON_OUTBOX_FSYNC_FAILED,
            details={"failure_reason": outbox.failure_reason},
        )

    # 3. Crash-before-WAL window (CASE DSN-CASE-02): no durable write evidence
    #    anywhere. Without a durable receipt this is NOT a "safe rejection" of
    #    a performed write — the operation was attempted and produced nothing
    #    durable; recovery re-runs it under the same operation ID.
    nothing_durable = (
        row.status is ChannelStatus.ABSENT
        and receipt.status is ChannelStatus.ABSENT
        and outbox.status is ChannelStatus.ABSENT
    )
    if nothing_durable:
        return DurabilityVerdict(
            outcome=DurabilityOutcome.REJECTED,
            reason_code=REASON_NOT_COMMITTED_NO_DURABLE_EVIDENCE,
            details={"operation_id": op_id, "channels": ["clinical_row", "ledger", "outbox"]},
        )

    # 4. Clinical row corrupt (torn write) — never inferred either way.
    if row.status is ChannelStatus.CORRUPT:
        return _indeterminate(REASON_CLINICAL_ROW_CORRUPT, operation_id=op_id)

    # 5. Outbox record corrupt — evidence integrity failure.
    if outbox.status is ChannelStatus.CORRUPT:
        return _indeterminate(REASON_INTERNAL_EVALUATION_ERROR, channel="outbox")

    # 6. Ledger corrupt (tampered receipt, CASE DSN-CASE-06): flag tamper,
    #    reconcile independently, never silently succeed.
    if receipt.status is ChannelStatus.CORRUPT:
        return _indeterminate(REASON_DECISION_RECEIPT_CORRUPT, operation_id=op_id)

    # 7. Timestamp anomalies: durable evidence must predate the reconciler and
    #    order consistently (intent -> WAL -> receipt, receipt -> outbox).
    if row.status is ChannelStatus.PRESENT:
        if row.wal_commit_logical_time > state.reconciler_logical_time:
            return _indeterminate(
                REASON_WAL_COMMIT_TIMESTAMP_ANOMALY,
                wal_commit_logical_time=row.wal_commit_logical_time,
                reconciler_logical_time=state.reconciler_logical_time,
            )
    if receipt.status is ChannelStatus.PRESENT:
        if receipt.receipt_logical_time > state.reconciler_logical_time:
            return _indeterminate(
                REASON_RECEIPT_TIMESTAMP_ANOMALY,
                receipt_logical_time=receipt.receipt_logical_time,
                reconciler_logical_time=state.reconciler_logical_time,
            )
        if row.status is ChannelStatus.PRESENT:
            if receipt.receipt_logical_time < row.wal_commit_logical_time:
                return _indeterminate(
                    REASON_RECEIPT_TIMESTAMP_ANOMALY,
                    receipt_logical_time=receipt.receipt_logical_time,
                    wal_commit_logical_time=row.wal_commit_logical_time,
                )
    if outbox.status is ChannelStatus.PRESENT:
        if outbox.recorded_logical_time > state.reconciler_logical_time:
            return _indeterminate(
                REASON_OUTBOX_TIMESTAMP_ANOMALY,
                recorded_logical_time=outbox.recorded_logical_time,
                reconciler_logical_time=state.reconciler_logical_time,
            )
        if row.status is ChannelStatus.PRESENT:
            if outbox.recorded_logical_time < row.wal_commit_logical_time:
                return _indeterminate(
                    REASON_OUTBOX_TIMESTAMP_ANOMALY,
                    recorded_logical_time=outbox.recorded_logical_time,
                    wal_commit_logical_time=row.wal_commit_logical_time,
                )
        applied_times = [
            d.delivered_logical_time
            for d in outbox.deliveries
            if d.effect_applied and d.delivered_logical_time < outbox.recorded_logical_time
        ]
        if applied_times:
            return _indeterminate(
                REASON_DELIVERY_TIMESTAMP_ANOMALY,
                min_delivered_logical_time=min(applied_times),
                recorded_logical_time=outbox.recorded_logical_time,
            )

    # 8. Cross-channel identity: all durable evidence must name this operation.
    durable_op_ids = {
        "clinical_row": row.operation_id,
        "decision_receipt": receipt.operation_id,
        "outbox": outbox.operation_id,
    }
    mismatched = {
        channel: found
        for channel, found in durable_op_ids.items()
        if found is not None and found != op_id
    }
    if mismatched:
        return _indeterminate(REASON_STATE_OPERATION_MISMATCH, mismatches=mismatched)

    # 9. Committed clinical row present: verify receipt binding.
    if row.status is ChannelStatus.PRESENT:
        if receipt.status is not ChannelStatus.PRESENT:
            # Committed row with no decision receipt: the ledger evidence is
            # missing, so durable success cannot be asserted (fail closed).
            return _indeterminate(
                REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW if receipt.status is ChannelStatus.ABSENT
                else REASON_MISSING_DECISION_RECEIPT,
                operation_id=op_id,
                row_version=row.row_version,
            )
        # Version binding (stale receipt detection).
        if receipt.row_version != row.row_version:
            return _indeterminate(
                REASON_STALE_RECEIPT_VERSION_MISMATCH,
                receipt_row_version=receipt.row_version,
                row_version=row.row_version,
            )
        # Consent epoch binding: the ledger must reference a known epoch.
        if receipt.consent_epoch > state.current_consent_epoch:
            return _indeterminate(
                REASON_CONSENT_EPOCH_ANOMALY,
                receipt_consent_epoch=receipt.consent_epoch,
                current_consent_epoch=state.current_consent_epoch,
            )
        # Decision lineage: a non-accept decision is authoritative rejection.
        if receipt.decision != RECEIPT_DECISION_ACCEPT:
            return DurabilityVerdict(
                outcome=DurabilityOutcome.REJECTED,
                reason_code=REASON_CONSENT_REVOKED_BEFORE_COMMIT
                if receipt.consent_epoch < intent.authorized_consent_epoch
                else REASON_RECEIPT_DECISION_CONFLICT,
                details={"receipt_decision": receipt.decision},
            )
        # Forensic digest binding (CASE DSN-CASE-06): the receipt's signed
        # transition digest must equal the committed row digest.
        if (
            receipt.stored_transition_digest is not None
            and receipt.stored_transition_digest != row.row_digest_sha256
        ):
            return _indeterminate(
                REASON_RECEIPT_DIGEST_MISMATCH,
                stored_transition_digest=receipt.stored_transition_digest,
                row_digest_sha256=row.row_digest_sha256,
            )
        # Outbox independence: a committed write still needs its outbox record
        # to exist durably (same transaction in the outbox pattern).
        if outbox.status is ChannelStatus.ABSENT:
            return _indeterminate(
                REASON_OUTBOX_RECORD_MISSING, operation_id=op_id, row_version=row.row_version
            )
        # Duplicate deliveries (CASE DSN-CASE-04): idempotence requires every
        # recorded effect to be identical.
        applied = [d for d in outbox.deliveries if d.effect_applied]
        applied_digests = {d.effect_receipt_digest for d in applied}
        if len(applied_digests) > 1:
            return _indeterminate(
                REASON_DUPLICATE_EFFECT_DIVERGENCE,
                distinct_effect_digests=sorted(digest for digest in applied_digests if digest),
            )
        if applied:
            outcome_reason = (
                REASON_COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT
                if len(applied) > 1
                else REASON_COMMITTED_EFFECT_APPLIED
            )
            effect_receipt = applied[0].effect_receipt_digest
        else:
            outcome_reason = REASON_COMMITTED_PENDING_DELIVERY
            effect_receipt = None
        return DurabilityVerdict(
            outcome=DurabilityOutcome.COMMITTED,
            reason_code=(
                REASON_COMMITTED_PRE_REVOCATION
                if state.current_consent_epoch > intent.authorized_consent_epoch
                else outcome_reason
            ),
            details={
                "operation_id": op_id,
                "row_version": row.row_version,
                "deliveries_recorded": len(outbox.deliveries),
                "effects_applied": len(applied),
                "effect_receipt_digest": effect_receipt,
            },
        )

    # 10. No committed row, but ledger/outbox evidence exists.
    if receipt.status is ChannelStatus.PRESENT:
        # Ledger receipt without a committed clinical row: either the receipt
        # is orphaned (written outside the row transaction) or the row was
        # lost after commit. Both are unresolved — never a rejection that
        # would allow a forbidden double effect, never a success.
        return _indeterminate(
            REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW,
            operation_id=op_id,
            receipt_row_version=receipt.row_version,
        )
    if outbox.status is ChannelStatus.PRESENT:
        # Outbox record without a committed clinical row contradicts the
        # atomic outbox write; the durable picture is torn.
        return _indeterminate(
            REASON_OUTBOX_ORPHAN_NO_CLINICAL_ROW, operation_id=op_id
        )
    # Partial durable evidence outside the enumerated cases cannot happen
    # (all channel/status combinations above are covered); keep fail-closed.
    return _indeterminate(REASON_INTERNAL_EVALUATION_ERROR, operation_id=op_id)


def evaluate_durability(write_intent: WriteIntent, durable_state: DurableState) -> DurabilityVerdict:
    """Map ``(write_intent, durable_state)`` to exactly one durable verdict.

    Fail-closed contract: malformed inputs, cross-channel disagreement,
    digest tampering and timestamp anomalies all yield ``INDETERMINATE`` (or,
    where durable evidence proves non-commit, ``REJECTED``) with a stable
    reason code — never an exception escaping to the caller, never a positive
    outcome inferred from an HTTP response or any non-durable signal.
    """

    try:
        intent_issues = _intent_issues(write_intent)
        if intent_issues:
            return _indeterminate(
                REASON_MALFORMED_WRITE_INTENT, invalid_fields=sorted(intent_issues)
            )
        state_issues = _state_issues(durable_state)
        if state_issues:
            return _indeterminate(
                REASON_MALFORMED_DURABLE_STATE, invalid_fields=sorted(state_issues)
            )
        return _evaluate_channels(write_intent, durable_state)
    except Exception as exc:  # noqa: BLE001 - fail-closed boundary
        return _indeterminate(REASON_INTERNAL_EVALUATION_ERROR, error_class=type(exc).__name__)


def reconcile(operation_id: str, state: DurableState) -> DurabilityVerdict:
    """Convenience reconciler for a durable snapshot without the intent record.

    Reconstructs the minimal intent envelope from the durable state itself
    (operation identity + observed epochs). Used when the original intent
    record was lost in the crash window; ambiguity still fails closed inside
    :func:`evaluate_durability`.
    """

    epoch = max(
        state.current_consent_epoch,
        state.clinical_row.consent_epoch_at_commit or 0,
        state.decision_receipt.consent_epoch or 0,
    )
    row_op = state.clinical_row.operation_id or operation_id
    receipt_op = state.decision_receipt.operation_id or operation_id
    outbox_op = state.outbox.operation_id or operation_id
    if len({row_op, receipt_op, outbox_op}) != 1:
        found = sorted({row_op, receipt_op, outbox_op})
        return _indeterminate(REASON_STATE_OPERATION_MISMATCH, mismatches={"recovered": found})
    intent = WriteIntent(
        operation_id=operation_id,
        tenant_id="recovered",
        principal_id="reconciler",
        purpose="recovery",
        authorized_consent_epoch=epoch,
        payload_digest_sha256=_synthetic_digest(operation_id),
        issued_logical_time=0,
    )
    return evaluate_durability(intent, state)


class CrashPoint:
    """Named crash cut points mirroring CASE_MATRIX DSN-CASE-02..07 windows."""

    NONE: Final[str] = "none"
    PRE_COMMIT: Final[str] = "pre_commit"
    POST_COMMIT_PRE_RESPONSE: Final[str] = "post_commit_pre_response"
    PRE_OUTBOX_DELIVERY: Final[str] = "pre_outbox_delivery"


CRASH_POINTS: Final[tuple[str, ...]] = (
    CrashPoint.NONE,
    CrashPoint.PRE_COMMIT,
    CrashPoint.POST_COMMIT_PRE_RESPONSE,
    CrashPoint.PRE_OUTBOX_DELIVERY,
)


@dataclasses.dataclass(frozen=True)
class HistoryEvent:
    """One recorded event in a crash/recovery episode.

    ``kind`` is one of ``WRITE_INTENT`` (payload holds a :class:`WriteIntent`
    dict), ``DURABLE_STATE`` (payload holds a :class:`DurableState` dict),
    ``CRASH`` (payload holds ``{"crash_point": <str>}``), ``DELIVER`` (at-least
    -once replay; payload holds a :class:`DeliveryReceipt` dict) or
    ``EVALUATION`` (payload holds a recorded :class:`DurabilityVerdict` dict).
    """

    kind: str
    logical_time: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "logical_time": self.logical_time,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> HistoryEvent:
        try:
            return cls(
                kind=payload["kind"],
                logical_time=payload["logical_time"],
                payload=dict(payload["payload"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed HistoryEvent payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class EventHistory:
    """A crash/recovery episode: ordered events plus the recovery horizon."""

    events: tuple[HistoryEvent, ...]
    reconciler_logical_time: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "reconciler_logical_time": self.reconciler_logical_time,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EventHistory:
        try:
            return cls(
                events=tuple(HistoryEvent.from_dict(e) for e in payload["events"]),
                reconciler_logical_time=payload["reconciler_logical_time"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed EventHistory payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class RecoveryVerdict:
    """Outcome of folding one :class:`EventHistory` (JSON-serializable)."""

    outcome: DurabilityOutcome
    reason_code: str
    last_intent: dict[str, Any] | None
    crash_points: tuple[str, ...]
    evaluations: tuple[dict[str, Any], ...]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "last_intent": self.last_intent,
            "crash_points": list(self.crash_points),
            "evaluations": list(self.evaluations),
            "details": dict(self.details),
        }


_KIND_INTENT: Final[str] = "WRITE_INTENT"
_KIND_STATE: Final[str] = "DURABLE_STATE"
_KIND_CRASH: Final[str] = "CRASH"
_KIND_DELIVER: Final[str] = "DELIVER"
_KIND_EVALUATION: Final[str] = "EVALUATION"
KNOWN_EVENT_KINDS: Final[tuple[str, ...]] = (
    _KIND_INTENT,
    _KIND_STATE,
    _KIND_CRASH,
    _KIND_DELIVER,
    _KIND_EVALUATION,
)


def _fold_delivery(state: DurableState, receipt: DeliveryReceipt) -> DurableState:
    """Record one delivery attempt in the outbox channel (at-least-once replay)."""

    outbox = state.outbox
    merged = tuple(sorted(outbox.deliveries + (receipt,), key=lambda d: d.attempt))
    new_outbox = dataclasses.replace(outbox, deliveries=merged)
    return dataclasses.replace(state, outbox=new_outbox)


def recover(history: EventHistory) -> RecoveryVerdict:
    """Fold a crash/recovery episode into one :class:`RecoveryVerdict`.

    The fold replays events in order: write intents set the adjudicated
    operation, crash markers only record the cut point, durable-state events
    replace the observed post-crash snapshot, ``DELIVER`` events append
    partial-effect receipts to the outbox channel, and recorded ``EVALUATION``
    events are preserved verbatim in the result. The final verdict is the
    durability evaluation of the last observed durable state against the last
    write intent. Incomplete, malformed or conflicting histories fail closed
    with a stable reason code.
    """

    try:
        if history.reconciler_logical_time < 0:
            return RecoveryVerdict(
                outcome=DurabilityOutcome.INDETERMINATE,
                reason_code=REASON_MALFORMED_HISTORY_EVENT,
                last_intent=None,
                crash_points=(),
                evaluations=(),
                details={"field": "reconciler_logical_time"},
            )
        last_intent: WriteIntent | None = None
        state: DurableState | None = None
        crash_points: list[str] = []
        evaluations: list[dict[str, Any]] = []
        for index, event in enumerate(history.events):
            if not _valid_int(event.logical_time) or not isinstance(event.payload, dict):
                return RecoveryVerdict(
                    outcome=DurabilityOutcome.INDETERMINATE,
                    reason_code=REASON_MALFORMED_HISTORY_EVENT,
                    last_intent=last_intent.to_dict() if last_intent else None,
                    crash_points=tuple(crash_points),
                    evaluations=tuple(evaluations),
                    details={"event_index": index},
                )
            if event.kind == _KIND_INTENT:
                try:
                    last_intent = WriteIntent.from_dict(event.payload)
                except ValueError:
                    return RecoveryVerdict(
                        outcome=DurabilityOutcome.INDETERMINATE,
                        reason_code=REASON_MALFORMED_HISTORY_EVENT,
                        last_intent=None,
                        crash_points=tuple(crash_points),
                        evaluations=tuple(evaluations),
                        details={"event_index": index, "kind": event.kind},
                    )
            elif event.kind == _KIND_STATE:
                try:
                    state = DurableState.from_dict(event.payload)
                except ValueError:
                    return RecoveryVerdict(
                        outcome=DurabilityOutcome.INDETERMINATE,
                        reason_code=REASON_MALFORMED_HISTORY_EVENT,
                        last_intent=last_intent.to_dict() if last_intent else None,
                        crash_points=tuple(crash_points),
                        evaluations=tuple(evaluations),
                        details={"event_index": index, "kind": event.kind},
                    )
            elif event.kind == _KIND_CRASH:
                crash_point = event.payload.get("crash_point")
                if crash_point not in CRASH_POINTS:
                    return RecoveryVerdict(
                        outcome=DurabilityOutcome.INDETERMINATE,
                        reason_code=REASON_UNKNOWN_HISTORY_EVENT,
                        last_intent=last_intent.to_dict() if last_intent else None,
                        crash_points=tuple(crash_points),
                        evaluations=tuple(evaluations),
                        details={"event_index": index, "crash_point": str(crash_point)},
                    )
                crash_points.append(str(crash_point))
            elif event.kind == _KIND_DELIVER:
                try:
                    receipt = DeliveryReceipt.from_dict(event.payload)
                except ValueError:
                    return RecoveryVerdict(
                        outcome=DurabilityOutcome.INDETERMINATE,
                        reason_code=REASON_MALFORMED_HISTORY_EVENT,
                        last_intent=last_intent.to_dict() if last_intent else None,
                        crash_points=tuple(crash_points),
                        evaluations=tuple(evaluations),
                        details={"event_index": index, "kind": event.kind},
                    )
                if state is not None:
                    state = _fold_delivery(state, receipt)
            elif event.kind == _KIND_EVALUATION:
                evaluations.append(dict(event.payload))
            else:
                return RecoveryVerdict(
                    outcome=DurabilityOutcome.INDETERMINATE,
                    reason_code=REASON_UNKNOWN_HISTORY_EVENT,
                    last_intent=last_intent.to_dict() if last_intent else None,
                    crash_points=tuple(crash_points),
                    evaluations=tuple(evaluations),
                    details={"event_index": index, "kind": str(event.kind)},
                )
        if last_intent is None or state is None:
            return RecoveryVerdict(
                outcome=DurabilityOutcome.INDETERMINATE,
                reason_code=REASON_HISTORY_INCOMPLETE,
                last_intent=last_intent.to_dict() if last_intent else None,
                crash_points=tuple(crash_points),
                evaluations=tuple(evaluations),
                details={"has_intent": last_intent is not None, "has_state": state is not None},
            )
        bounded_state = dataclasses.replace(
            state, reconciler_logical_time=history.reconciler_logical_time
        )
        verdict = evaluate_durability(last_intent, bounded_state)
        return RecoveryVerdict(
            outcome=verdict.outcome,
            reason_code=verdict.reason_code,
            last_intent=last_intent.to_dict(),
            crash_points=tuple(crash_points),
            evaluations=tuple(evaluations),
            details=verdict.details,
        )
    except Exception as exc:  # noqa: BLE001 - fail-closed boundary
        return RecoveryVerdict(
            outcome=DurabilityOutcome.INDETERMINATE,
            reason_code=REASON_INTERNAL_EVALUATION_ERROR,
            last_intent=None,
            crash_points=(),
            evaluations=(),
            details={"error_class": type(exc).__name__},
        )


def verdict_sha256(verdict: DurabilityVerdict | RecoveryVerdict) -> str:
    """Stable digest binding a verdict to its content (audit/observability)."""

    if isinstance(verdict, RecoveryVerdict):
        payload: dict[str, Any] = verdict.to_dict()
    else:
        payload = verdict.to_dict()
    return _sha256_text(_canonical_json(payload))


def _demo() -> dict[str, Any]:
    """Deterministic self-check across the four CASE_MATRIX crash windows."""

    op = "op:demo-0001"
    digest = _synthetic_digest(op)
    intent = WriteIntent(
        operation_id=op,
        tenant_id="synthetic-tenant",
        principal_id="synthetic-actor",
        purpose="self_care",
        authorized_consent_epoch=3,
        payload_digest_sha256=digest,
        issued_logical_time=10,
    )

    def blank_state(epoch: int = 3, now: int = 100) -> DurableState:
        return DurableState(
            clinical_row=ClinicalRowState(status=ChannelStatus.ABSENT),
            decision_receipt=DecisionReceipt(status=ChannelStatus.ABSENT),
            outbox=OutboxState(status=ChannelStatus.ABSENT),
            current_consent_epoch=epoch,
            reconciler_logical_time=now,
        )

    committed_state = DurableState(
        clinical_row=ClinicalRowState(
            status=ChannelStatus.PRESENT,
            operation_id=op,
            row_version=1,
            wal_commit_logical_time=20,
            consent_epoch_at_commit=3,
            row_digest_sha256=digest,
        ),
        decision_receipt=DecisionReceipt(
            status=ChannelStatus.PRESENT,
            operation_id=op,
            row_version=1,
            consent_epoch=3,
            decision=RECEIPT_DECISION_ACCEPT,
            receipt_logical_time=21,
            receipt_digest_sha256=_synthetic_digest(op + ":receipt"),
            stored_transition_digest=digest,
        ),
        outbox=OutboxState(
            status=ChannelStatus.PRESENT,
            operation_id=op,
            recorded_logical_time=20,
            deliveries=(
                DeliveryReceipt(
                    operation_id=op,
                    attempt=1,
                    effect_applied=True,
                    delivered_logical_time=30,
                    effect_receipt_digest=_synthetic_digest(op + ":effect"),
                ),
            ),
        ),
        current_consent_epoch=3,
        reconciler_logical_time=100,
    )

    scenarios: dict[str, DurableState] = {
        CrashPoint.NONE: committed_state,
        CrashPoint.PRE_COMMIT: blank_state(),
        CrashPoint.POST_COMMIT_PRE_RESPONSE: dataclasses.replace(
            committed_state,
            outbox=OutboxState(
                status=ChannelStatus.PRESENT,
                operation_id=op,
                recorded_logical_time=20,
            ),
        ),
        CrashPoint.PRE_OUTBOX_DELIVERY: dataclasses.replace(
            committed_state,
            outbox=OutboxState(
                status=ChannelStatus.PRESENT,
                operation_id=op,
                recorded_logical_time=20,
            ),
        ),
    }
    return {
        "version": STATE_MACHINE_VERSION,
        "results": {name: evaluate_durability(intent, st).to_dict() for name, st in scenarios.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DSN-X01 durable state machine self-check")
    parser.add_argument("--demo", action="store_true", help="run the deterministic self-check")
    parser.add_argument("--outdir", default=None, help="write state_spec.json to this directory")
    args = parser.parse_args(argv)
    if not args.demo and args.outdir is None:
        parser.error("nothing to do: pass --demo and/or --outdir")
    payload = _demo()
    if args.outdir is not None:
        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "state_spec.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps({"version": payload["version"], "n_results": len(payload["results"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
