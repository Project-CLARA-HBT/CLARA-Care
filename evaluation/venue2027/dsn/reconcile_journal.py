"""DSN-X06_reconcile_journal — three-view reconciliation with explicit repair plans.

Purpose
-------
Candidate recovery routine for the DSN 2027 study "Recoverable Safety Journals
for Crash-Consistent AI-Mediated Health-State Mutations" (RQ2;
research/venue2027/VENUES/dsn/RESEARCH_BLUEPRINT.md,
research/venue2027/VENUES/dsn/TASKS/DSN-X06_reconcile_journal.md). After a
crash and bounded recovery, three independent durable views of one operation
may be read:

- ``clinical`` — the committed clinical row channel (WAL-backed mutation).
- ``ledger``   — the immutable versioned decision receipt (decision lineage).
- ``outbox``   — the transactional outbox record with delivery receipts.

:func:`reconcile` compares the three views and returns exactly one
:class:`ReconcileVerdict`:

- ``CONSISTENT``   — all present views carry matching, well-formed evidence
  for the same operation; durable success is asserted only from durable
  evidence, never from an ACK, HTTP response or a missing receipt.
- ``REPAIRABLE``   — the views are incomplete but not contradictory, and a
  deterministic repair plan (ordered, idempotent, keyed by the immutable
  operation ID) can converge them. The plan is *proposed*, never applied
  here; applying it is the caller's durably journaled responsibility.
- ``IRRECONCILABLE`` — the views positively disagree (identity, version,
  epoch, digest or ordering). No repair is proposed: any mechanical "fix"
  would launder contradicting evidence.
- ``INDETERMINATE`` — ambiguous or malformed evidence (fail-closed default).
  A missing receipt is never treated as durable success and INDETERMINATE is
  never coerced into CONSISTENT or a "safe rejection".

Allowed input
-------------
Typed, JSON-serializable dataclasses: :class:`ClinicalView`, :class:`LedgerView`,
:class:`OutboxView` (``from_dict`` constructors provided; structural errors
raise ``ValueError`` at construction). All timestamps are logical integers
supplied by the caller — no hidden clock, no randomness, no I/O, no provider
calls. Digests bind views together without carrying clinical payload content.
The routine is pure: identical inputs always yield an equal verdict, so a
re-evaluation after a plan is applied (idempotently, keyed by the stable
operation ID) returns the same result for the same durable picture.

Failure semantics
-----------------
Semantically invalid evidence never raises: every failure mode maps to a
stable ``reason_code`` on :class:`ReconcileVerdict` (malformed inputs,
cross-view disagreement, digest tampering, timestamp anomalies, repair-plan
ambiguity). :func:`reconcile` is additionally wrapped in a fail-closed guard —
an unexpected internal error yields ``INDETERMINATE`` /
``INTERNAL_RECONCILIATION_ERROR``, never a silent acceptance.

Version
-------
``RECONCILE_JOURNAL_VERSION = "clara.dsn.reconcile-journal-v1"`` (additive-only
evolution within v1; the verdict shape is version-pinned for the oracle).
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
from typing import Any, Final

RECONCILE_JOURNAL_VERSION: Final[str] = "clara.dsn.reconcile-journal-v1"

DECISION_ACCEPT: Final[str] = "ACCEPT"

VIEW_CLINICAL: Final[str] = "clinical"
VIEW_LEDGER: Final[str] = "ledger"
VIEW_OUTBOX: Final[str] = "outbox"


class ReconcileOutcome(enum.StrEnum):
    """Four-way reconciliation outcome over the three durable views."""

    CONSISTENT = "CONSISTENT"
    REPAIRABLE = "REPAIRABLE"
    IRRECONCILABLE = "IRRECONCILABLE"
    INDETERMINATE = "INDETERMINATE"


class ViewStatus(enum.StrEnum):
    """Durable status of one view read after recovery.

    ABSENT — no durable record. PRESENT — durable, well-formed record.
    CORRUPT — record exists but integrity checks failed (torn write / tamper).
    """

    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    CORRUPT = "CORRUPT"


# --- Stable reason codes (fail-closed registry) -----------------------------

REASON_CONSISTENT_ALL_VIEWS_AGREE: Final[str] = "CONSISTENT_ALL_VIEWS_AGREE"
REASON_CONSISTENT_PENDING_DELIVERY: Final[str] = "CONSISTENT_PENDING_DELIVERY"
REASON_REPAIRABLE_MISSING_OUTBOX: Final[str] = "REPAIRABLE_MISSING_OUTBOX"
REASON_REPAIRABLE_MISSING_LEDGER: Final[str] = "REPAIRABLE_MISSING_LEDGER"
REASON_REPAIRABLE_MISSING_OUTBOX_AND_LEDGER: Final[str] = "REPAIRABLE_MISSING_OUTBOX_AND_LEDGER"
REASON_REPAIRABLE_OUTBOX_PENDING: Final[str] = "REPAIRABLE_OUTBOX_PENDING"
REASON_IRRECONCILABLE_OPERATION_MISMATCH: Final[str] = "IRRECONCILABLE_OPERATION_MISMATCH"
REASON_IRRECONCILABLE_LEDGER_DISAGREES: Final[str] = "IRRECONCILABLE_LEDGER_DISAGREES"
REASON_IRRECONCILABLE_ROW_VERSION_MISMATCH: Final[str] = "IRRECONCILABLE_ROW_VERSION_MISMATCH"
REASON_IRRECONCILABLE_DIGEST_MISMATCH: Final[str] = "IRRECONCILABLE_DIGEST_MISMATCH"
REASON_IRRECONCILABLE_EFFECT_DIVERGENCE: Final[str] = "IRRECONCILABLE_EFFECT_DIVERGENCE"
REASON_IRRECONCILABLE_ORPHAN_LEDGER: Final[str] = "IRRECONCILABLE_ORPHAN_LEDGER"
REASON_IRRECONCILABLE_ORPHAN_OUTBOX: Final[str] = "IRRECONCILABLE_ORPHAN_OUTBOX"
REASON_IRRECONCILABLE_OUTBOX_REVOKED: Final[str] = "IRRECONCILABLE_OUTBOX_REVOKED"
REASON_IRRECONCILABLE_CONFLICTING_ABSENCE: Final[str] = "IRRECONCILABLE_CONFLICTING_ABSENCE"
REASON_INDETERMINATE_CLINICAL_CORRUPT: Final[str] = "INDETERMINATE_CLINICAL_CORRUPT"
REASON_INDETERMINATE_LEDGER_CORRUPT: Final[str] = "INDETERMINATE_LEDGER_CORRUPT"
REASON_INDETERMINATE_OUTBOX_CORRUPT: Final[str] = "INDETERMINATE_OUTBOX_CORRUPT"
REASON_INDETERMINATE_TIMESTAMP_ANOMALY: Final[str] = "INDETERMINATE_TIMESTAMP_ANOMALY"
REASON_INDETERMINATE_NO_EVIDENCE: Final[str] = "INDETERMINATE_NO_EVIDENCE"
REASON_MALFORMED_CLINICAL_VIEW: Final[str] = "MALFORMED_CLINICAL_VIEW"
REASON_MALFORMED_LEDGER_VIEW: Final[str] = "MALFORMED_LEDGER_VIEW"
REASON_MALFORMED_OUTBOX_VIEW: Final[str] = "MALFORMED_OUTBOX_VIEW"
REASON_MALFORMED_CONSENT_EPOCH: Final[str] = "MALFORMED_CONSENT_EPOCH"
REASON_MALFORMED_RECONCILER_TIME: Final[str] = "MALFORMED_RECONCILER_TIME"
REASON_INTERNAL_RECONCILIATION_ERROR: Final[str] = "INTERNAL_RECONCILIATION_ERROR"

REASON_CODES: Final[tuple[str, ...]] = (
    REASON_CONSISTENT_ALL_VIEWS_AGREE,
    REASON_CONSISTENT_PENDING_DELIVERY,
    REASON_REPAIRABLE_MISSING_OUTBOX,
    REASON_REPAIRABLE_MISSING_LEDGER,
    REASON_REPAIRABLE_MISSING_OUTBOX_AND_LEDGER,
    REASON_REPAIRABLE_OUTBOX_PENDING,
    REASON_IRRECONCILABLE_OPERATION_MISMATCH,
    REASON_IRRECONCILABLE_LEDGER_DISAGREES,
    REASON_IRRECONCILABLE_ROW_VERSION_MISMATCH,
    REASON_IRRECONCILABLE_DIGEST_MISMATCH,
    REASON_IRRECONCILABLE_EFFECT_DIVERGENCE,
    REASON_IRRECONCILABLE_ORPHAN_LEDGER,
    REASON_IRRECONCILABLE_ORPHAN_OUTBOX,
    REASON_IRRECONCILABLE_OUTBOX_REVOKED,
    REASON_IRRECONCILABLE_CONFLICTING_ABSENCE,
    REASON_INDETERMINATE_CLINICAL_CORRUPT,
    REASON_INDETERMINATE_LEDGER_CORRUPT,
    REASON_INDETERMINATE_OUTBOX_CORRUPT,
    REASON_INDETERMINATE_TIMESTAMP_ANOMALY,
    REASON_INDETERMINATE_NO_EVIDENCE,
    REASON_MALFORMED_CLINICAL_VIEW,
    REASON_MALFORMED_LEDGER_VIEW,
    REASON_MALFORMED_OUTBOX_VIEW,
    REASON_MALFORMED_CONSENT_EPOCH,
    REASON_MALFORMED_RECONCILER_TIME,
    REASON_INTERNAL_RECONCILIATION_ERROR,
)


# --- Repair action registry (deterministic plans only) -----------------------

ACTION_MARK_LEDGER_COMMITTED: Final[str] = "MARK_LEDGER_COMMITTED"
ACTION_ENQUEUE_OUTBOX: Final[str] = "ENQUEUE_OUTBOX"
ACTION_RECORD_DELIVERY: Final[str] = "RECORD_DELIVERY"
ACTION_ESCALATE_MANUAL_REVIEW: Final[str] = "ESCALATE_MANUAL_REVIEW"

KNOWN_ACTIONS: Final[tuple[str, ...]] = (
    ACTION_MARK_LEDGER_COMMITTED,
    ACTION_ENQUEUE_OUTBOX,
    ACTION_RECORD_DELIVERY,
    ACTION_ESCALATE_MANUAL_REVIEW,
)


class RepairAction(enum.StrEnum):
    """Deterministic, idempotent repair primitives keyed by the operation ID."""

    MARK_LEDGER_COMMITTED = ACTION_MARK_LEDGER_COMMITTED
    ENQUEUE_OUTBOX = ACTION_ENQUEUE_OUTBOX
    RECORD_DELIVERY = ACTION_RECORD_DELIVERY
    ESCALATE_MANUAL_REVIEW = ACTION_ESCALATE_MANUAL_REVIEW


@dataclasses.dataclass(frozen=True)
class RepairStep:
    """One ordered, idempotent step of a deterministic repair plan."""

    order: int
    action: str
    view: str
    operation_id: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "view": self.view,
            "operation_id": self.operation_id,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RepairStep:
        try:
            return cls(
                order=payload["order"],
                action=payload["action"],
                view=payload["view"],
                operation_id=payload["operation_id"],
                detail=payload["detail"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed RepairStep payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class RepairPlan:
    """Explicit, deterministic repair plan (empty for non-REPAIRABLE verdicts)."""

    steps: tuple[RepairStep, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RepairPlan:
        try:
            return cls(steps=tuple(RepairStep.from_dict(s) for s in payload.get("steps", ())))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed RepairPlan payload: {exc}") from exc


# --- Durable view records ----------------------------------------------------

_OP_ID_ALLOWED: Final[str] = "operation identifiers admit [A-Za-z0-9._:@/-]{1,128}"
_OP_ID_MAX: Final[int] = 128


def _valid_op_id(value: Any) -> bool:
    if not isinstance(value, str) or not (1 <= len(value) <= _OP_ID_MAX):
        return False
    return all(c.isalnum() or c in "._:@/-" for c in value)


def _valid_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


def _valid_int(value: Any, *, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_label(value: Any) -> bool:
    return _valid_op_id(value)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def synthetic_digest(label: str) -> str:
    """Deterministic synthetic digest for fixtures (never real clinical data)."""

    return _sha256_text("clara.dsn.synthetic:" + label)


@dataclasses.dataclass(frozen=True)
class ClinicalView:
    """Committed clinical row channel (the WAL-backed mutation itself)."""

    status: ViewStatus
    operation_id: str | None = None
    row_version: int | None = None
    wal_commit_logical_time: int | None = None
    row_digest_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "operation_id": self.operation_id,
            "row_version": self.row_version,
            "wal_commit_logical_time": self.wal_commit_logical_time,
            "row_digest_sha256": self.row_digest_sha256,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ClinicalView:
        try:
            return cls(
                status=ViewStatus(payload["status"]),
                operation_id=payload.get("operation_id"),
                row_version=payload.get("row_version"),
                wal_commit_logical_time=payload.get("wal_commit_logical_time"),
                row_digest_sha256=payload.get("row_digest_sha256"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed ClinicalView payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class LedgerView:
    """Immutable versioned decision receipt (the ledger / decision lineage)."""

    status: ViewStatus
    operation_id: str | None = None
    row_version: int | None = None
    decision: str | None = None
    receipt_logical_time: int | None = None
    stored_transition_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "operation_id": self.operation_id,
            "row_version": self.row_version,
            "decision": self.decision,
            "receipt_logical_time": self.receipt_logical_time,
            "stored_transition_digest": self.stored_transition_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LedgerView:
        try:
            return cls(
                status=ViewStatus(payload["status"]),
                operation_id=payload.get("operation_id"),
                row_version=payload.get("row_version"),
                decision=payload.get("decision"),
                receipt_logical_time=payload.get("receipt_logical_time"),
                stored_transition_digest=payload.get("stored_transition_digest"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed LedgerView payload: {exc}") from exc


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
class OutboxView:
    """Transactional outbox record with its partial-effect delivery receipts."""

    status: ViewStatus
    operation_id: str | None = None
    recorded_logical_time: int | None = None
    deliveries: tuple[DeliveryReceipt, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "operation_id": self.operation_id,
            "recorded_logical_time": self.recorded_logical_time,
            "deliveries": [d.to_dict() for d in self.deliveries],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OutboxView:
        try:
            return cls(
                status=ViewStatus(payload["status"]),
                operation_id=payload.get("operation_id"),
                recorded_logical_time=payload.get("recorded_logical_time"),
                deliveries=tuple(
                    DeliveryReceipt.from_dict(d) for d in payload.get("deliveries", ())
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed OutboxView payload: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class ReconcileVerdict:
    """Exactly one outcome, stable reason code and a JSON-serializable body."""

    outcome: ReconcileOutcome
    reason_code: str
    details: dict[str, Any]
    repair_plan: RepairPlan

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "details": dict(self.details),
            "repair_plan": self.repair_plan.to_dict(),
            "version": RECONCILE_JOURNAL_VERSION,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ReconcileVerdict:
        try:
            return cls(
                outcome=ReconcileOutcome(payload["outcome"]),
                reason_code=payload["reason_code"],
                details=dict(payload.get("details", {})),
                repair_plan=RepairPlan.from_dict(payload.get("repair_plan", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed ReconcileVerdict payload: {exc}") from exc


def _empty_plan() -> RepairPlan:
    return RepairPlan(steps=())


def _consistent(reason_code: str, **details: Any) -> ReconcileVerdict:
    return ReconcileVerdict(
        outcome=ReconcileOutcome.CONSISTENT,
        reason_code=reason_code,
        details=dict(details),
        repair_plan=_empty_plan(),
    )


def _repairable(reason_code: str, plan: RepairPlan, **details: Any) -> ReconcileVerdict:
    return ReconcileVerdict(
        outcome=ReconcileOutcome.REPAIRABLE,
        reason_code=reason_code,
        details=dict(details),
        repair_plan=plan,
    )


def _irreconcilable(reason_code: str, **details: Any) -> ReconcileVerdict:
    return ReconcileVerdict(
        outcome=ReconcileOutcome.IRRECONCILABLE,
        reason_code=reason_code,
        details=dict(details),
        repair_plan=_empty_plan(),
    )


def _indeterminate(reason_code: str, **details: Any) -> ReconcileVerdict:
    return ReconcileVerdict(
        outcome=ReconcileOutcome.INDETERMINATE,
        reason_code=reason_code,
        details=dict(details),
        repair_plan=_empty_plan(),
    )


# --- Structural validation ---------------------------------------------------


def _clinical_issues(view: ClinicalView) -> list[str]:
    issues: list[str] = []
    if not isinstance(view.status, ViewStatus):
        issues.append("status")
        return issues
    if view.status is ViewStatus.ABSENT:
        if any(
            v is not None
            for v in (
                view.operation_id,
                view.row_version,
                view.wal_commit_logical_time,
                view.row_digest_sha256,
            )
        ):
            issues.append("absent_carries_payload")
    elif view.status is ViewStatus.PRESENT:
        if not _valid_op_id(view.operation_id):
            issues.append("operation_id")
        if not _valid_int(view.row_version):
            issues.append("row_version")
        if not _valid_int(view.wal_commit_logical_time):
            issues.append("wal_commit_logical_time")
        if not _valid_sha256(view.row_digest_sha256):
            issues.append("row_digest_sha256")
    elif view.status is ViewStatus.CORRUPT:
        if not _valid_op_id(view.operation_id):
            issues.append("operation_id")
    return issues


def _ledger_issues(view: LedgerView) -> list[str]:
    issues: list[str] = []
    if not isinstance(view.status, ViewStatus):
        issues.append("status")
        return issues
    if view.status is ViewStatus.ABSENT:
        if any(
            v is not None
            for v in (
                view.operation_id,
                view.row_version,
                view.decision,
                view.receipt_logical_time,
                view.stored_transition_digest,
            )
        ):
            issues.append("absent_carries_payload")
    elif view.status is ViewStatus.PRESENT:
        if not _valid_op_id(view.operation_id):
            issues.append("operation_id")
        if not _valid_int(view.row_version):
            issues.append("row_version")
        if not _valid_label(view.decision):
            issues.append("decision")
        if not _valid_int(view.receipt_logical_time):
            issues.append("receipt_logical_time")
        if view.stored_transition_digest is not None and not _valid_sha256(
            view.stored_transition_digest
        ):
            issues.append("stored_transition_digest")
    elif view.status is ViewStatus.CORRUPT:
        if not _valid_op_id(view.operation_id):
            issues.append("operation_id")
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


def _outbox_issues(view: OutboxView) -> list[str]:
    issues: list[str] = []
    if not isinstance(view.status, ViewStatus):
        issues.append("status")
        return issues
    if view.status is ViewStatus.ABSENT:
        if view.operation_id is not None or view.deliveries:
            issues.append("absent_carries_payload")
    else:
        if not _valid_op_id(view.operation_id):
            issues.append("operation_id")
        if view.status is ViewStatus.PRESENT and not _valid_int(view.recorded_logical_time):
            issues.append("recorded_logical_time")
        if view.status is ViewStatus.CORRUPT and view.deliveries:
            issues.append("corrupt_carries_deliveries")
    for delivery in view.deliveries:
        issues.extend(_delivery_issues(delivery))
    return issues


def _input_issues(clinical: ClinicalView, ledger: LedgerView, outbox: OutboxView) -> list[str]:
    """Prefixed structural issues across the three views (``view.field``)."""

    issues: list[str] = []
    for view_name, view_issues in (
        (VIEW_CLINICAL, _clinical_issues(clinical)),
        (VIEW_LEDGER, _ledger_issues(ledger)),
        (VIEW_OUTBOX, _outbox_issues(outbox)),
    ):
        issues.extend(f"{view_name}.{issue}" for issue in view_issues)
    return issues


# --- Core reconciliation (pure, fail-closed) ---------------------------------


def _timestamp_anomalies(
    clinical: ClinicalView, ledger: LedgerView, outbox: OutboxView, reconciler_logical_time: int
) -> dict[str, Any] | None:
    """Ordering checks: durable evidence must predate the reconciler and order
    consistently (intent -> WAL -> ledger receipt, WAL -> outbox record)."""

    if clinical.status is ViewStatus.PRESENT:
        if clinical.wal_commit_logical_time > reconciler_logical_time:
            return {
                "anomaly": "wal_commit_after_reconciler",
                "wal_commit_logical_time": clinical.wal_commit_logical_time,
                "reconciler_logical_time": reconciler_logical_time,
            }
    if ledger.status is ViewStatus.PRESENT:
        if ledger.receipt_logical_time > reconciler_logical_time:
            return {
                "anomaly": "receipt_after_reconciler",
                "receipt_logical_time": ledger.receipt_logical_time,
                "reconciler_logical_time": reconciler_logical_time,
            }
        if clinical.status is ViewStatus.PRESENT and (
            ledger.receipt_logical_time < clinical.wal_commit_logical_time
        ):
            return {
                "anomaly": "receipt_before_wal_commit",
                "receipt_logical_time": ledger.receipt_logical_time,
                "wal_commit_logical_time": clinical.wal_commit_logical_time,
            }
    if outbox.status is ViewStatus.PRESENT:
        if outbox.recorded_logical_time > reconciler_logical_time:
            return {
                "anomaly": "outbox_after_reconciler",
                "recorded_logical_time": outbox.recorded_logical_time,
                "reconciler_logical_time": reconciler_logical_time,
            }
        if clinical.status is ViewStatus.PRESENT and (
            outbox.recorded_logical_time < clinical.wal_commit_logical_time
        ):
            return {
                "anomaly": "outbox_before_wal_commit",
                "recorded_logical_time": outbox.recorded_logical_time,
                "wal_commit_logical_time": clinical.wal_commit_logical_time,
            }
        applied_before_record = [
            d.delivered_logical_time
            for d in outbox.deliveries
            if d.effect_applied and d.delivered_logical_time < outbox.recorded_logical_time
        ]
        if applied_before_record:
            return {
                "anomaly": "delivery_before_outbox_record",
                "min_delivered_logical_time": min(applied_before_record),
                "recorded_logical_time": outbox.recorded_logical_time,
            }
    return None


def _operation_mismatch(
    operation_id: str, clinical: ClinicalView, ledger: LedgerView, outbox: OutboxView
) -> dict[str, str] | None:
    found: dict[str, str] = {}
    for name, value in (
        (VIEW_CLINICAL, clinical.operation_id),
        (VIEW_LEDGER, ledger.operation_id),
        (VIEW_OUTBOX, outbox.operation_id),
    ):
        if value is not None and value != operation_id:
            found[name] = value
    return found or None


def _ledger_disagrees_with_clinical(
    operation_id: str, clinical: ClinicalView, ledger: LedgerView
) -> str | None:
    """Positive cross-view contradictions between row and decision receipt."""

    if clinical.status is not ViewStatus.PRESENT or ledger.status is not ViewStatus.PRESENT:
        return None
    if ledger.row_version != clinical.row_version:
        return "row_version_mismatch"
    if (
        ledger.stored_transition_digest is not None
        and ledger.stored_transition_digest != clinical.row_digest_sha256
    ):
        return "transition_digest_mismatch"
    return None


def _deterministic_plan(
    operation_id: str,
    clinical: ClinicalView,
    ledger: LedgerView,
    outbox: OutboxView,
    repair_missing_ledger: bool,
) -> RepairPlan:
    """Build the canonical ordered repair plan for a REPAIRABLE picture.

    Order is fixed by dependency: (1) stamp the missing ledger receipt from
    the committed row (only when the row is the sole authoritative anchor),
    (2) enqueue the missing outbox record from the committed row, (3) record
    the pending delivery once the consumer reports its idempotent effect.
    Every step is idempotent: re-applying it to an already-repaired view is a
    no-op, and re-running :func:`reconcile` after each applied step yields the
    same plan for the remaining gaps.
    """

    steps: list[RepairStep] = []
    order = 0
    if repair_missing_ledger:
        steps.append(
            RepairStep(
                order=order,
                action=ACTION_MARK_LEDGER_COMMITTED,
                view=VIEW_LEDGER,
                operation_id=operation_id,
                detail=(
                    "write ledger receipt bound to committed row "
                    f"version={clinical.row_version} digest={clinical.row_digest_sha256}"
                ),
            )
        )
        order += 1
    if outbox.status is ViewStatus.ABSENT:
        steps.append(
            RepairStep(
                order=order,
                action=ACTION_ENQUEUE_OUTBOX,
                view=VIEW_OUTBOX,
                operation_id=operation_id,
                detail=(
                    "re-queue outbox record bound to committed row "
                    f"row_version={clinical.row_version} (idempotent by operation ID)"
                ),
            )
        )
        order += 1
    if outbox.status is ViewStatus.PRESENT and not any(d.effect_applied for d in outbox.deliveries):
        steps.append(
            RepairStep(
                order=order,
                action=ACTION_RECORD_DELIVERY,
                view=VIEW_OUTBOX,
                operation_id=operation_id,
                detail=(
                    "run idempotent consumer delivery keyed by operation ID and "
                    "record its effect receipt (no-op if already applied)"
                ),
            )
        )
        order += 1
    return RepairPlan(steps=tuple(steps))


def _reconcile_views(
    clinical: ClinicalView,
    ledger: LedgerView,
    outbox: OutboxView,
    current_consent_epoch: int,
    reconciler_logical_time: int,
) -> ReconcileVerdict:
    """Core three-view comparison; every branch fails closed on ambiguity."""

    # 1. Structural validation (malformed views never become decisions).
    issues = _input_issues(clinical, ledger, outbox)
    if issues:
        reason = {
            VIEW_CLINICAL: REASON_MALFORMED_CLINICAL_VIEW,
            VIEW_LEDGER: REASON_MALFORMED_LEDGER_VIEW,
            VIEW_OUTBOX: REASON_MALFORMED_OUTBOX_VIEW,
        }.get(issues[0].split(".", 1)[0], REASON_INTERNAL_RECONCILIATION_ERROR)
        return _indeterminate(reason, invalid_fields=sorted(issues))
    if not _valid_int(current_consent_epoch):
        return _indeterminate(REASON_MALFORMED_CONSENT_EPOCH, current_consent_epoch=None)
    if not _valid_int(reconciler_logical_time):
        return _indeterminate(REASON_MALFORMED_RECONCILER_TIME, reconciler_logical_time=None)

    # 2. Corruption: evidence integrity failures are never interpreted either
    #    way (tamper / torn write) — fail closed with the offending view.
    if clinical.status is ViewStatus.CORRUPT:
        return _indeterminate(REASON_INDETERMINATE_CLINICAL_CORRUPT)
    if ledger.status is ViewStatus.CORRUPT:
        return _indeterminate(REASON_INDETERMINATE_LEDGER_CORRUPT)
    if outbox.status is ViewStatus.CORRUPT:
        return _indeterminate(REASON_INDETERMINATE_OUTBOX_CORRUPT)

    # 3. Nothing durable anywhere: an empty recovery picture is ambiguous, not
    #    a success and not a "safe rejection" (crash cut point unknown).
    if (
        clinical.status is ViewStatus.ABSENT
        and ledger.status is ViewStatus.ABSENT
        and outbox.status is ViewStatus.ABSENT
    ):
        return _indeterminate(
            REASON_INDETERMINATE_NO_EVIDENCE, views=[VIEW_CLINICAL, VIEW_LEDGER, VIEW_OUTBOX]
        )

    # 4. Operation identity: every present view must name the same operation.
    operation_id = clinical.operation_id or ledger.operation_id or outbox.operation_id
    mismatches = _operation_mismatch(operation_id, clinical, ledger, outbox)
    if mismatches:
        return _irreconcilable(
            REASON_IRRECONCILABLE_OPERATION_MISMATCH, operation_id=operation_id, mismatches=mismatches
        )

    # 5. Timestamp ordering anomalies (torn-window forensics).
    anomaly = _timestamp_anomalies(clinical, ledger, outbox, reconciler_logical_time)
    if anomaly is not None:
        return _indeterminate(REASON_INDETERMINATE_TIMESTAMP_ANOMALY, **anomaly)

    # 6. Committed clinical row present: reconcile ledger and outbox against it.
    if clinical.status is ViewStatus.PRESENT:
        row_version = clinical.row_version
        if ledger.status is ViewStatus.ABSENT:
            # Missing ledger: the receipt evidence is absent, so durable
            # success can never be asserted on the row alone (fail closed).
            # Repairable only when the row is the sole anchor: the outbox, if
            # present, must agree with the row (same op, no contradiction).
            if outbox.status is ViewStatus.PRESENT:
                if outbox.operation_id != operation_id:
                    return _irreconcilable(
                        REASON_IRRECONCILABLE_OPERATION_MISMATCH,
                        operation_id=operation_id,
                        mismatches={VIEW_OUTBOX: str(outbox.operation_id)},
                    )
                if outbox.recorded_logical_time < clinical.wal_commit_logical_time:
                    return _indeterminate(
                        REASON_INDETERMINATE_TIMESTAMP_ANOMALY,
                        anomaly="outbox_before_wal_commit",
                        recorded_logical_time=outbox.recorded_logical_time,
                        wal_commit_logical_time=clinical.wal_commit_logical_time,
                    )
            plan = _deterministic_plan(
                operation_id, clinical, ledger, outbox, repair_missing_ledger=True
            )
            reason = (
                REASON_REPAIRABLE_MISSING_LEDGER
                if outbox.status is not ViewStatus.ABSENT
                else REASON_REPAIRABLE_MISSING_OUTBOX_AND_LEDGER
            )
            return _repairable(
                reason,
                plan,
                operation_id=operation_id,
                row_version=row_version,
                repair_scope=["ledger", "outbox"],
            )
        if ledger.status is ViewStatus.PRESENT:
            # Positive disagreement between ledger and clinical row.
            disagreement = _ledger_disagrees_with_clinical(operation_id, clinical, ledger)
            if disagreement == "row_version_mismatch":
                return _irreconcilable(
                    REASON_IRRECONCILABLE_ROW_VERSION_MISMATCH,
                    operation_id=operation_id,
                    ledger_row_version=ledger.row_version,
                    clinical_row_version=clinical.row_version,
                )
            if disagreement == "transition_digest_mismatch":
                return _irreconcilable(
                    REASON_IRRECONCILABLE_DIGEST_MISMATCH,
                    operation_id=operation_id,
                    stored_transition_digest=ledger.stored_transition_digest,
                    row_digest_sha256=clinical.row_digest_sha256,
                )
            # Ledger decision lineage: only a durable ACCEPT receipt counts.
            if ledger.decision != DECISION_ACCEPT:
                return _irreconcilable(
                    REASON_IRRECONCILABLE_LEDGER_DISAGREES,
                    operation_id=operation_id,
                    ledger_decision=str(ledger.decision),
                )
            if outbox.status is ViewStatus.ABSENT:
                # Missing outbox row with a committed ledger and row: the
                # canonical REPAIRABLE case (re-queue from the committed row).
                plan = _deterministic_plan(
                    operation_id, clinical, ledger, outbox, repair_missing_ledger=False
                )
                return _repairable(
                    REASON_REPAIRABLE_MISSING_OUTBOX,
                    plan,
                    operation_id=operation_id,
                    row_version=row_version,
                    repair_scope=[VIEW_OUTBOX],
                )
            # All three views present and agreeing on identity/version/digest.
            applied = [d for d in outbox.deliveries if d.effect_applied]
            applied_digests = {d.effect_receipt_digest for d in applied}
            if len(applied_digests) > 1:
                return _irreconcilable(
                    REASON_IRRECONCILABLE_EFFECT_DIVERGENCE,
                    operation_id=operation_id,
                    distinct_effect_digests=sorted(
                        digest for digest in applied_digests if digest is not None
                    ),
                )
            if applied:
                return _consistent(
                    REASON_CONSISTENT_ALL_VIEWS_AGREE,
                    operation_id=operation_id,
                    row_version=row_version,
                    deliveries_recorded=len(outbox.deliveries),
                    effects_applied=len(applied),
                    effect_receipt_digest=applied[0].effect_receipt_digest,
                )
            return _consistent(
                REASON_CONSISTENT_PENDING_DELIVERY,
                operation_id=operation_id,
                row_version=row_version,
                deliveries_recorded=len(outbox.deliveries),
                effects_applied=0,
                effect_receipt_digest=None,
            )

    # 7. No committed clinical row.
    if ledger.status is ViewStatus.PRESENT:
        # Ledger receipt without a committed row: either an orphan receipt
        # written outside the row transaction or a lost row. Both are
        # unresolved contradictions — repairing either direction could
        # license a forbidden duplicate effect, so never propose a plan.
        return _irreconcilable(
            REASON_IRRECONCILABLE_ORPHAN_LEDGER,
            operation_id=str(ledger.operation_id),
            ledger_row_version=ledger.row_version,
        )
    if outbox.status is ViewStatus.PRESENT:
        # Outbox record without a committed row contradicts the atomic
        # outbox write; the durable picture is torn, not repairable.
        return _irreconcilable(
            REASON_IRRECONCILABLE_ORPHAN_OUTBOX, operation_id=str(outbox.operation_id)
        )
    # Partial evidence outside the enumerated cases cannot occur (all
    # status combinations are covered above); keep fail-closed.
    return _indeterminate(REASON_INTERNAL_RECONCILIATION_ERROR)


def reconcile(
    clinical: ClinicalView,
    ledger: LedgerView,
    outbox: OutboxView,
    *,
    current_consent_epoch: int = 0,
    reconciler_logical_time: int = 0,
) -> ReconcileVerdict:
    """Compare the three durable views after recovery and decide one outcome.

    Parameters
    ----------
    clinical, ledger, outbox:
        Post-recovery durable views (:class:`ClinicalView`, :class:`LedgerView`,
        :class:`OutboxView`).
    current_consent_epoch:
        Governance epoch observed at recovery time (validated, unused for
        repair decisions; a negative value fails closed).
    reconciler_logical_time:
        Logical recovery horizon; durable timestamps after it are anomalies.

    Returns
    -------
    ReconcileVerdict
        Exactly one of ``CONSISTENT`` (no repair plan), ``REPAIRABLE`` (with
        an explicit, deterministic, idempotent repair plan), ``IRRECONCILABLE``
        (views positively disagree; no plan is ever proposed) or
        ``INDETERMINATE`` (ambiguous/malformed evidence, with a reason code).
        Durable success is never invented: a missing receipt never counts as
        success, and INDETERMINATE is never coerced to CONSISTENT.
    """

    try:
        return _reconcile_views(
            clinical, ledger, outbox, current_consent_epoch, reconciler_logical_time
        )
    except Exception as exc:  # noqa: BLE001 - fail-closed boundary
        return _indeterminate(
            REASON_INTERNAL_RECONCILIATION_ERROR, error_class=type(exc).__name__
        )


def verdict_sha256(verdict: ReconcileVerdict) -> str:
    """Stable digest binding a verdict to its content (audit/observability)."""

    return _sha256_text(_canonical_json(verdict.to_dict()))


def _demo() -> dict[str, Any]:
    """Deterministic self-check across representative recovery pictures."""

    op = "op:demo-dsn-x06-0001"
    row_digest = synthetic_digest(op + ":row")
    effect_digest = synthetic_digest(op + ":effect")
    consistent = reconcile(
        ClinicalView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            row_version=1,
            wal_commit_logical_time=20,
            row_digest_sha256=row_digest,
        ),
        LedgerView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            row_version=1,
            decision=DECISION_ACCEPT,
            receipt_logical_time=21,
            stored_transition_digest=row_digest,
        ),
        OutboxView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            recorded_logical_time=20,
            deliveries=(
                DeliveryReceipt(
                    operation_id=op,
                    attempt=1,
                    effect_applied=True,
                    delivered_logical_time=30,
                    effect_receipt_digest=effect_digest,
                ),
            ),
        ),
        current_consent_epoch=3,
        reconciler_logical_time=100,
    )
    missing_outbox = reconcile(
        ClinicalView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            row_version=1,
            wal_commit_logical_time=20,
            row_digest_sha256=row_digest,
        ),
        LedgerView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            row_version=1,
            decision=DECISION_ACCEPT,
            receipt_logical_time=21,
            stored_transition_digest=row_digest,
        ),
        OutboxView(status=ViewStatus.ABSENT),
        current_consent_epoch=3,
        reconciler_logical_time=100,
    )
    disagreeing_ledger = reconcile(
        ClinicalView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            row_version=2,
            wal_commit_logical_time=20,
            row_digest_sha256=row_digest,
        ),
        LedgerView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            row_version=1,
            decision=DECISION_ACCEPT,
            receipt_logical_time=21,
            stored_transition_digest=row_digest,
        ),
        OutboxView(
            status=ViewStatus.PRESENT,
            operation_id=op,
            recorded_logical_time=20,
        ),
        current_consent_epoch=3,
        reconciler_logical_time=100,
    )
    return {
        "version": RECONCILE_JOURNAL_VERSION,
        "results": {
            "consistent_triple": consistent.to_dict(),
            "missing_outbox_row": missing_outbox.to_dict(),
            "ledger_disagrees": disagreeing_ledger.to_dict(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DSN-X06 three-view reconciliation self-check")
    parser.add_argument("--json", action="store_true", help="print the self-check as JSON")
    args = parser.parse_args(argv)
    report = _demo()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for name, result in report["results"].items():
            print(f"{name}: {result['outcome']} ({result['reason_code']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
