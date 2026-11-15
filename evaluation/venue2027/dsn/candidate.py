"""DSN-candidate — recoverable safety journal (proposed mechanism, arm B3).

Purpose
-------
P04 candidate mechanism for the DSN 2027 study "Recoverable Safety Journals for
Crash-Consistent AI-Mediated Health-State Mutations"
(``research/venue2027/VENUES/dsn/RESEARCH_BLUEPRINT.md``, strong-baseline arm
B3; task contract ``research/venue2027/VENUES/dsn/TASKS/DSN-candidate.md``).
Recoverability is a safety property of the *joint* clinical row, immutable
decision lineage and asynchronous side-effect record — not of one database
commit. The candidate makes a per-operation, hash-chained **safety journal**
the durable authority for the decision lineage: every governed transition
appends an entry (INTENT, COMMIT, OUTBOX_RECORD, EFFECT_APPLIED, ABORT) whose
digest is chained to its predecessor, and the side effect is recorded in the
journal *write-ahead* (before the effect is applied to the injected store).
A pure recoverable-outcome function folds the journal into exactly one verdict
— ``COMMITTED``, ``REJECTED`` or ``INDETERMINATE`` — and retries are keyed to
the immutable operation ID, so a re-run after any crash window resumes the
episode instead of repeating it.

Algorithm (pseudocode; maps 1:1 to the blueprint's method architecture)
-----------------------------------------------------------------------
::

    # EXECUTE (arm-B3 executor; every APPEND below is a durable journal write)
    #   J <- injected journal (empty on a fresh episode)
    #   defects <- VERIFY(J)                      # seq contiguity, hash chain
    #   if defects: REFUSE (fail closed, no mutation)
    #   if INTENT not in J: APPEND(J, INTENT(payload_digest, authorized_epoch))
    #   crash(pre_commit)?              -> STOP    # DSN-CASE-02 window
    #   if ABORT in J: STOP                       # rejection is stable
    #   if COMMIT not in J:
    #       if epoch_at_commit > authorized_epoch:
    #           APPEND(J, ABORT(revocation)); STOP          # DSN-CASE-05
    #       APPEND(J, COMMIT(row_version=1, epoch, payload_digest))
    #   MATERIALIZE clinical row from journal (idempotent by operation ID)
    #   crash(post_commit_pre_response)? -> STOP  # DSN-CASE-03 window
    #   if OUTBOX_RECORD not in J: APPEND(J, OUTBOX_RECORD)
    #   for attempt in delivery_schedule:         # at-least-once replay
    #       crash(pre_outbox_delivery) before first attempt? -> STOP
    #       if EFFECT_APPLIED(d) in J: record delivery as DEDUPED; continue
    #       APPEND(J, EFFECT_APPLIED(attempt, d)) # write-ahead effect record
    #       crash(mid_effect)?              -> STOP # effect-ack-lost window
    #       APPLY effect to injected store (idempotent by operation ID)
    #
    # RESUME := EXECUTE again with the same intent/schedule and the returned
    #   journal; process memory is lost at the crash but the durable journal
    #   and durable stores survive, so the episode continues exactly once.
    #
    # RECOVERABLE_OUTCOME(J, intent) — pure adjudication, fail closed:
    #   defects <- VERIFY(J)
    #   structural defect or semantic contradiction -> INDETERMINATE
    #   first entry must be the matching INTENT     -> else INDETERMINATE
    #   fold entries in seq order:
    #     ABORT recorded                            -> REJECTED (revocation)
    #     COMMIT stamped with a later consent epoch -> REJECTED (forbidden write)
    #     COMMIT present, effect recorded           -> COMMITTED (applied)
    #     COMMIT present, effect pending            -> COMMITTED (pending delivery)
    #     INTENT only / empty journal               -> REJECTED (retriable)
    #   every ambiguous or tampered picture stays INDETERMINATE — never a
    #   positive outcome, never a coerced "safe rejection".

Mechanism-isolation ablation
----------------------------
:func:`ablation_no_journal_execute` runs the same schedule with the journal
removed (blueprint arm B0's failure mode: DB transaction only + fire-and-forget
side effect). With no durable decision lineage the retry after a crash window
cannot adjudicate anything (``recoverable_outcome_available=False``) and the
non-idempotent consumer applies one effect per delivery (duplicated side
effects under broker replay). The test suite uses this to prove the journal —
not the idempotent store alone — is the load-bearing mechanism for exactly-once
commit plus adjudicable outcomes.

Candidate design only: this module encodes a mechanism and its executable
invariants. It makes NO empirical claims (no measured rates, no dataset
results, no latency numbers). Benchmarks belong to the DSN-X03/X04/X05 arms.

Independence
------------
This module NEVER imports the independent oracle
(``evaluation/venue2027/dsn/independent_oracle.py``), the reference state
machine, the reconciler or any held-out label file; ``test_candidate.py``
asserts this statically (AST scan) and at runtime (fresh-interpreter import).
No wall clock, randomness, network, database or provider access: timestamps
are caller-supplied logical integers, stores are injected, digests are
synthetic (sha256 of candidate-namespaced strings, never patient data).

Allowed input
-------------
Typed, JSON-serializable dataclasses: :class:`WriteIntent`,
:class:`JournalEntry`, :class:`SafetyJournal`, :class:`DurableStores`,
:class:`ExecutionReport` and :class:`RecoveryOutcome` (``from_dict``
constructors provided; structural errors raise :class:`CandidateError` with a
stable reason code). :func:`execute_operation` accepts an intent, an optional
existing journal, an optional injected :class:`DurableStores`, one crash
window (``none`` / ``pre_commit`` / ``post_commit_pre_response`` /
``pre_outbox_delivery`` / ``mid_effect``), a delivery schedule of positive
attempt numbers (duplicates allowed — at-least-once replay) and the consent
epoch observed at commit time (governance state is externalized policy).
:func:`run_candidate(case, ctx)` maps a strict JSON case schema onto one full
episode (execute -> crash -> resume -> adjudicate) and returns the shared
harness :class:`Outcome`; unknown case keys fail closed.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. ``execute_operation`` refuses
(wiring-level :class:`CandidateError`) malformed intents, unknown crash
windows, malformed schedules and journals that fail verification — it never
mutates durable state on unverified evidence. ``recoverable_outcome`` never
raises: malformed input, chain breaks, seq gaps, foreign entries, intent
mismatch, effect-without-commit, abort/commit contradictions, duplicate-effect
divergence and any unexpected internal error all yield ``INDETERMINATE`` (or,
where durable evidence proves non-commit, a retriable ``REJECTED``) with a
stable reason code. A corrupted journal is NEVER laundered into a positive
outcome and never into a "safe rejection" of a write that may have happened.
Tail truncation of the journal is modelled as a crash window (a legal prefix),
not corruption; interior tampering is corruption.

Version
-------
``CANDIDATE_VERSION = "1.0.0"`` (additive-only within 1.x);
``CANDIDATE_ID = "dsn-recoverable-safety-journal"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome

__all__ = [
    "ABLATION_ID",
    "ABORT",
    "CANDIDATE_ID",
    "CANDIDATE_VERSION",
    "COMMIT",
    "CORRUPTION_MODES",
    "CRASH_MID_EFFECT",
    "CRASH_NONE",
    "CRASH_POINTS",
    "CRASH_POST_COMMIT_PRE_RESPONSE",
    "CRASH_PRE_COMMIT",
    "CRASH_PRE_OUTBOX_DELIVERY",
    "CandidateError",
    "DurableStores",
    "EFFECT_APPLIED",
    "ExecutionReport",
    "INTENT",
    "JOURNAL_VERSION",
    "JournalEntry",
    "OUTBOX_RECORD",
    "REASON_CODES",
    "RECOVERY_REASON_CODES",
    "RecoveryOutcome",
    "SafetyJournal",
    "WriteIntent",
    "ablation_no_journal_execute",
    "corrupt_journal",
    "describe_mechanism",
    "execute_operation",
    "recoverable_outcome",
    "run_candidate",
    "verify_journal",
]

CANDIDATE_ID: Final[str] = "dsn-recoverable-safety-journal"
CANDIDATE_VERSION: Final[str] = "1.0.0"
ABLATION_ID: Final[str] = "dsn-ablation-no-journal"
JOURNAL_VERSION: Final[str] = "clara.dsn.safety-journal-v1"

#: Journal entry kinds (the durable decision lineage).
INTENT: Final[str] = "INTENT"
COMMIT: Final[str] = "COMMIT"
OUTBOX_RECORD: Final[str] = "OUTBOX_RECORD"
EFFECT_APPLIED: Final[str] = "EFFECT_APPLIED"
ABORT: Final[str] = "ABORT"
ENTRY_KINDS: Final[tuple[str, ...]] = (INTENT, COMMIT, OUTBOX_RECORD, EFFECT_APPLIED, ABORT)

#: Crash windows (one cut point per episode; ``none`` = no crash).
CRASH_NONE: Final[str] = "none"
CRASH_PRE_COMMIT: Final[str] = "pre_commit"
CRASH_POST_COMMIT_PRE_RESPONSE: Final[str] = "post_commit_pre_response"
CRASH_PRE_OUTBOX_DELIVERY: Final[str] = "pre_outbox_delivery"
CRASH_MID_EFFECT: Final[str] = "mid_effect"
CRASH_POINTS: Final[tuple[str, ...]] = (
    CRASH_NONE,
    CRASH_PRE_COMMIT,
    CRASH_POST_COMMIT_PRE_RESPONSE,
    CRASH_PRE_OUTBOX_DELIVERY,
    CRASH_MID_EFFECT,
)

#: Verdicts of the recoverable-outcome function.
VERDICT_COMMITTED: Final[str] = "COMMITTED"
VERDICT_REJECTED: Final[str] = "REJECTED"
VERDICT_INDETERMINATE: Final[str] = "INDETERMINATE"

#: Executor refusal reason codes (wiring-level CandidateError).
RC_JOURNAL_CORRUPT = "JOURNAL_CORRUPT"
RC_JOURNAL_MALFORMED = "MALFORMED_JOURNAL"
RC_MALFORMED_WRITE_INTENT = "MALFORMED_WRITE_INTENT"
RC_CRASH_POINT_UNKNOWN = "CRASH_POINT_UNKNOWN"
RC_DELIVERY_SCHEDULE_MALFORMED = "DELIVERY_SCHEDULE_MALFORMED"
RC_CONSENT_EPOCH_MALFORMED = "CONSENT_EPOCH_MALFORMED"
RC_CASE_NOT_AN_OBJECT = "CASE_NOT_AN_OBJECT"
RC_CASE_UNKNOWN_FIELD = "CASE_UNKNOWN_FIELD"
RC_CASE_MISSING_FIELD = "CASE_MISSING_FIELD"
RC_CASE_BAD_FIELD = "CASE_BAD_FIELD"
RC_CORRUPTION_SPEC_MALFORMED = "CORRUPTION_SPEC_MALFORMED"
RC_INTERNAL_CANDIDATE_ERROR = "INTERNAL_CANDIDATE_ERROR"

#: Adjudication reason codes (first-class RecoveryOutcome.reason_code values).
RC_JOURNAL_SEQ_GAP = "JOURNAL_SEQ_GAP"
RC_JOURNAL_CHAIN_BREAK = "JOURNAL_CHAIN_BREAK"
RC_JOURNAL_DIGEST_MISMATCH = "JOURNAL_DIGEST_MISMATCH"
RC_JOURNAL_UNKNOWN_KIND = "JOURNAL_UNKNOWN_KIND"
RC_JOURNAL_FOREIGN_ENTRY = "JOURNAL_FOREIGN_ENTRY"
RC_INTENT_NOT_FIRST = "JOURNAL_INTENT_NOT_FIRST"
RC_JOURNAL_INTENT_MISMATCH = "JOURNAL_INTENT_MISMATCH"
RC_CONSENT_REVOKED_BEFORE_COMMIT = "CONSENT_REVOKED_BEFORE_COMMIT"
RC_FORBIDDEN_WRITE_POST_REVOCATION = "FORBIDDEN_WRITE_POST_REVOCATION"
RC_NOT_COMMITTED_NO_DURABLE_EVIDENCE = "NOT_COMMITTED_NO_DURABLE_EVIDENCE"
RC_COMMITTED_EFFECT_APPLIED = "COMMITTED_EFFECT_APPLIED"
RC_COMMITTED_PENDING_DELIVERY = "COMMITTED_PENDING_DELIVERY"
RC_COMMIT_PAYLOAD_MALFORMED = "COMMIT_PAYLOAD_MALFORMED"
RC_DUPLICATE_COMMIT_RECORD = "DUPLICATE_COMMIT_RECORD"
RC_ABORT_COMMIT_CONTRADICTION = "ABORT_COMMIT_CONTRADICTION"
RC_OUTBOX_WITHOUT_COMMIT = "OUTBOX_WITHOUT_COMMIT"
RC_EFFECT_WITHOUT_COMMIT = "EFFECT_WITHOUT_COMMIT"
RC_DUPLICATE_EFFECT_DIVERGENCE = "DUPLICATE_EFFECT_DIVERGENCE"

REASON_CODES: Final[tuple[str, ...]] = (
    RC_JOURNAL_CORRUPT,
    RC_JOURNAL_MALFORMED,
    RC_MALFORMED_WRITE_INTENT,
    RC_CRASH_POINT_UNKNOWN,
    RC_DELIVERY_SCHEDULE_MALFORMED,
    RC_CONSENT_EPOCH_MALFORMED,
    RC_CASE_NOT_AN_OBJECT,
    RC_CASE_UNKNOWN_FIELD,
    RC_CASE_MISSING_FIELD,
    RC_CASE_BAD_FIELD,
    RC_CORRUPTION_SPEC_MALFORMED,
    RC_INTERNAL_CANDIDATE_ERROR,
)

RECOVERY_REASON_CODES: Final[tuple[str, ...]] = (
    RC_JOURNAL_CORRUPT,
    RC_JOURNAL_SEQ_GAP,
    RC_JOURNAL_CHAIN_BREAK,
    RC_JOURNAL_DIGEST_MISMATCH,
    RC_JOURNAL_UNKNOWN_KIND,
    RC_JOURNAL_FOREIGN_ENTRY,
    RC_INTENT_NOT_FIRST,
    RC_JOURNAL_INTENT_MISMATCH,
    RC_MALFORMED_WRITE_INTENT,
    RC_CONSENT_REVOKED_BEFORE_COMMIT,
    RC_FORBIDDEN_WRITE_POST_REVOCATION,
    RC_NOT_COMMITTED_NO_DURABLE_EVIDENCE,
    RC_COMMITTED_EFFECT_APPLIED,
    RC_COMMITTED_PENDING_DELIVERY,
    RC_COMMIT_PAYLOAD_MALFORMED,
    RC_DUPLICATE_COMMIT_RECORD,
    RC_ABORT_COMMIT_CONTRADICTION,
    RC_OUTBOX_WITHOUT_COMMIT,
    RC_EFFECT_WITHOUT_COMMIT,
    RC_DUPLICATE_EFFECT_DIVERGENCE,
    RC_INTERNAL_CANDIDATE_ERROR,
)

GENESIS_PREV_DIGEST: Final[str] = "0" * 64

_OP_ID_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._:@/-]{1,128}")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")


class CandidateError(ValueError):
    """Wiring-level refusal with a stable reason code (never an outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


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

    return _sha256_text("clara.dsn.candidate:" + label)


def _effect_digest(operation_id: str) -> str:
    """Stable synthetic effect receipt digest keyed by the operation ID."""

    return _sha256_text("clara.dsn.candidate.effect:" + operation_id)


def _intent_issues(intent: WriteIntent) -> list[str]:
    issues: list[str] = []
    if not _valid_label(intent.operation_id):
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


# ---------------------------------------------------------------------------
# Typed inputs / outputs (JSON-serializable)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class WriteIntent:
    """Governed write intent; retries for the same operation reuse it verbatim."""

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
    def from_dict(cls, payload: Mapping[str, Any]) -> WriteIntent:
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
            raise CandidateError(
                RC_MALFORMED_WRITE_INTENT, f"malformed WriteIntent payload: {exc}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class JournalEntry:
    """One hash-chained durable lineage record.

    ``entry_digest`` covers the journal version, sequence number, operation,
    kind, payload, logical time and the predecessor digest; any interior
    tampering breaks the chain and is reported by :func:`verify_journal`.
    """

    seq: int
    operation_id: str
    kind: str
    payload: dict[str, Any]
    at_logical_time: int
    prev_entry_digest: str
    entry_digest: str

    def digest_preimage(self) -> str:
        base = {
            "journal_version": JOURNAL_VERSION,
            "seq": self.seq,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "payload": self.payload,
            "at_logical_time": self.at_logical_time,
            "prev_entry_digest": self.prev_entry_digest,
        }
        return _canonical_json(base)

    def compute_digest(self) -> str:
        return _sha256_text(self.digest_preimage())

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "payload": dict(self.payload),
            "at_logical_time": self.at_logical_time,
            "prev_entry_digest": self.prev_entry_digest,
            "entry_digest": self.entry_digest,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> JournalEntry:
        try:
            entry = cls(
                seq=payload["seq"],
                operation_id=payload["operation_id"],
                kind=payload["kind"],
                payload=dict(payload["payload"]),
                at_logical_time=payload["at_logical_time"],
                prev_entry_digest=payload["prev_entry_digest"],
                entry_digest=payload["entry_digest"],
            )
        except (KeyError, TypeError) as exc:
            raise CandidateError(
                RC_JOURNAL_MALFORMED, f"malformed JournalEntry payload: {exc}"
            ) from exc
        structural = []
        if not _valid_int(entry.seq):
            structural.append("seq")
        if not _valid_label(entry.operation_id):
            structural.append("operation_id")
        if not isinstance(entry.kind, str):
            structural.append("kind")
        if not _valid_int(entry.at_logical_time):
            structural.append("at_logical_time")
        if not _valid_sha256(entry.prev_entry_digest):
            structural.append("prev_entry_digest")
        if not _valid_sha256(entry.entry_digest):
            structural.append("entry_digest")
        if structural:
            raise CandidateError(
                RC_JOURNAL_MALFORMED, f"invalid JournalEntry fields: {sorted(structural)}"
            )
        return entry


class SafetyJournal:
    """Append-only per-operation journal shard (functional: append returns new)."""

    def __init__(self, entries: Sequence[JournalEntry] = ()) -> None:
        self._entries: tuple[JournalEntry, ...] = tuple(entries)

    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        return self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def append(
        self, kind: str, operation_id: str, payload: Mapping[str, Any], at_logical_time: int
    ) -> SafetyJournal:
        if kind not in ENTRY_KINDS:
            raise CandidateError(RC_JOURNAL_MALFORMED, f"unknown entry kind: {kind}")
        prev_digest = self._entries[-1].entry_digest if self._entries else GENESIS_PREV_DIGEST
        entry = JournalEntry(
            seq=len(self._entries),
            operation_id=operation_id,
            kind=kind,
            payload=dict(payload),
            at_logical_time=at_logical_time,
            prev_entry_digest=prev_digest,
            entry_digest="",
        )
        entry = dataclasses.replace(entry, entry_digest=entry.compute_digest())
        return SafetyJournal(self._entries + (entry,))

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_version": JOURNAL_VERSION,
            "entries": [entry.to_dict() for entry in self._entries],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SafetyJournal:
        try:
            raw_entries = payload["entries"]
        except (KeyError, TypeError) as exc:
            raise CandidateError(
                RC_JOURNAL_MALFORMED, f"malformed SafetyJournal payload: {exc}"
            ) from exc
        if not isinstance(raw_entries, list):
            raise CandidateError(RC_JOURNAL_MALFORMED, "entries must be a list")
        return cls(tuple(JournalEntry.from_dict(raw) for raw in raw_entries))


@dataclasses.dataclass
class DurableStores:
    """Injected durable stores (clinical rows + effect sink) that survive crashes.

    Both materializations are idempotent by the immutable operation ID: a
    re-write of an existing row or effect is refused (returns ``False``) and
    never counted, so store counters accumulate actual mutations only.
    """

    rows: dict[str, int] = dataclasses.field(default_factory=dict)
    effects: dict[str, str] = dataclasses.field(default_factory=dict)
    row_write_count: int = 0
    effect_apply_count: int = 0

    def write_row(self, operation_id: str, row_version: int) -> bool:
        if operation_id in self.rows:
            return False
        self.rows[operation_id] = row_version
        self.row_write_count += 1
        return True

    def apply_effect(self, operation_id: str, effect_receipt_digest: str) -> bool:
        if operation_id in self.effects:
            return False
        self.effects[operation_id] = effect_receipt_digest
        self.effect_apply_count += 1
        return True

    def row_version(self, operation_id: str) -> int | None:
        return self.rows.get(operation_id)

    def effect_digest(self, operation_id: str) -> str | None:
        return self.effects.get(operation_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": dict(self.rows),
            "effects": dict(self.effects),
            "row_write_count": self.row_write_count,
            "effect_apply_count": self.effect_apply_count,
        }


@dataclasses.dataclass(frozen=True)
class ExecutionReport:
    """One executor episode (JSON-serializable via to_dict)."""

    journal: SafetyJournal
    crash_point: str
    resumed: bool
    stopped_at: str
    row_writes: int
    effect_applications: int
    deliveries_observed: int
    deliveries_deduped: int
    steps: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal": self.journal.to_dict(),
            "crash_point": self.crash_point,
            "resumed": self.resumed,
            "stopped_at": self.stopped_at,
            "row_writes": self.row_writes,
            "effect_applications": self.effect_applications,
            "deliveries_observed": self.deliveries_observed,
            "deliveries_deduped": self.deliveries_deduped,
            "steps": [dict(step) for step in self.steps],
        }


@dataclasses.dataclass(frozen=True)
class RecoveryOutcome:
    """Exactly one recoverable verdict with a stable reason code."""

    outcome: str
    reason_code: str
    retriable: bool
    details: dict[str, Any]

    def __post_init__(self) -> None:
        if self.outcome not in (VERDICT_COMMITTED, VERDICT_REJECTED, VERDICT_INDETERMINATE):
            raise CandidateError(RC_INTERNAL_CANDIDATE_ERROR, f"unknown verdict {self.outcome!r}")
        if self.reason_code not in RECOVERY_REASON_CODES:
            raise CandidateError(
                RC_INTERNAL_CANDIDATE_ERROR, f"unknown reason code {self.reason_code!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "retriable": self.retriable,
            "details": dict(self.details),
        }


# ---------------------------------------------------------------------------
# Journal verification (structural integrity of the hash chain)
# ---------------------------------------------------------------------------


def verify_journal(
    journal: SafetyJournal, operation_id: str | None = None
) -> tuple[dict[str, Any], ...]:
    """Return the tuple of structural defects (empty tuple = verified chain).

    Checks sequence contiguity from 0, genesis and linkage of the hash chain,
    digest recomputation, known entry kinds and (when ``operation_id`` is
    given) that every entry belongs to that operation's shard.
    """

    defects: list[dict[str, Any]] = []
    prev_digest: str | None = None
    for position, entry in enumerate(journal.entries):
        if entry.seq != position:
            defects.append({"code": RC_JOURNAL_SEQ_GAP, "position": position, "seq": entry.seq})
        expected_prev = prev_digest if prev_digest is not None else GENESIS_PREV_DIGEST
        if entry.prev_entry_digest != expected_prev:
            defects.append({"code": RC_JOURNAL_CHAIN_BREAK, "seq": entry.seq})
        if entry.compute_digest() != entry.entry_digest:
            defects.append({"code": RC_JOURNAL_DIGEST_MISMATCH, "seq": entry.seq})
        if entry.kind not in ENTRY_KINDS:
            defects.append({"code": RC_JOURNAL_UNKNOWN_KIND, "seq": entry.seq})
        if operation_id is not None and entry.operation_id != operation_id:
            defects.append(
                {
                    "code": RC_JOURNAL_FOREIGN_ENTRY,
                    "seq": entry.seq,
                    "entry_operation_id": entry.operation_id,
                }
            )
        prev_digest = entry.entry_digest
    return tuple(defects)


# ---------------------------------------------------------------------------
# Executor (arm B3): execute one episode; resume = call again with the journal
# ---------------------------------------------------------------------------


def _validated_schedule(delivery_schedule: Sequence[int]) -> tuple[int, ...]:
    if not isinstance(delivery_schedule, (list, tuple)):  # noqa: UP038 - legacy tuple form
        raise CandidateError(RC_DELIVERY_SCHEDULE_MALFORMED, "delivery_schedule must be a list")
    schedule = tuple(delivery_schedule)
    for attempt in schedule:
        if not _valid_int(attempt, minimum=1):
            raise CandidateError(
                RC_DELIVERY_SCHEDULE_MALFORMED,
                f"delivery attempts must be positive ints, got {attempt!r}",
            )
    return schedule


def _validated_epoch(consent_epoch_at_commit: int | None, intent: WriteIntent) -> int:
    if consent_epoch_at_commit is None:
        return intent.authorized_consent_epoch
    if not _valid_int(consent_epoch_at_commit):
        raise CandidateError(RC_CONSENT_EPOCH_MALFORMED, "consent_epoch_at_commit")
    return consent_epoch_at_commit


def _report(
    journal: SafetyJournal,
    crash_point: str,
    resumed: bool,
    stopped_at: str,
    counts: dict[str, int],
    steps: list[dict[str, Any]],
) -> ExecutionReport:
    return ExecutionReport(
        journal=journal,
        crash_point=crash_point,
        resumed=resumed,
        stopped_at=stopped_at,
        row_writes=counts["row_writes"],
        effect_applications=counts["effect_applications"],
        deliveries_observed=counts["deliveries_observed"],
        deliveries_deduped=counts["deliveries_deduped"],
        steps=tuple(steps),
    )


def execute_operation(
    intent: WriteIntent,
    *,
    crash_point: str = CRASH_NONE,
    delivery_schedule: Sequence[int] = (),
    journal: SafetyJournal | None = None,
    stores: DurableStores | None = None,
    consent_epoch_at_commit: int | None = None,
) -> ExecutionReport:
    """Run one episode of the arm-B3 executor; resume = call again with ``journal``.

    Raises :class:`CandidateError` (never mutates state) for malformed intents,
    unknown crash windows, malformed schedules/epochs and journals that fail
    :func:`verify_journal`. The crash window cuts the episode after the named
    durable step; the returned journal is the surviving durable artifact.
    """

    intent_issues = _intent_issues(intent)
    if intent_issues:
        raise CandidateError(RC_MALFORMED_WRITE_INTENT, f"invalid fields: {sorted(intent_issues)}")
    if crash_point not in CRASH_POINTS:
        raise CandidateError(RC_CRASH_POINT_UNKNOWN, f"crash_point {crash_point!r}")
    schedule = _validated_schedule(delivery_schedule)
    epoch_at_commit = _validated_epoch(consent_epoch_at_commit, intent)
    journal = journal if journal is not None else SafetyJournal()
    stores = stores if stores is not None else DurableStores()

    defects = verify_journal(journal, intent.operation_id)
    if defects:
        raise CandidateError(RC_JOURNAL_CORRUPT, _canonical_json(list(defects)))

    resumed = len(journal) > 0
    counts = {
        "row_writes": 0,
        "effect_applications": 0,
        "deliveries_observed": 0,
        "deliveries_deduped": 0,
    }
    steps: list[dict[str, Any]] = []
    op = intent.operation_id

    def _has(kind: str) -> bool:
        return any(entry.kind == kind for entry in journal.entries)

    def _effect_digests() -> set[str]:
        return {
            entry.payload["effect_receipt_digest"]
            for entry in journal.entries
            if entry.kind == EFFECT_APPLIED and "effect_receipt_digest" in entry.payload
        }

    def _append(kind: str, payload: Mapping[str, Any]) -> None:
        nonlocal journal
        at_logical_time = intent.issued_logical_time + len(journal)
        journal = journal.append(kind, op, payload, at_logical_time)
        steps.append({"step": "APPEND", "kind": kind, "seq": len(journal) - 1})

    def _stop(stop_reason: str) -> ExecutionReport:
        return _report(journal, crash_point, resumed, stop_reason, counts, steps)

    if not _has(INTENT):
        _append(
            INTENT,
            {
                "payload_digest_sha256": intent.payload_digest_sha256,
                "authorized_consent_epoch": intent.authorized_consent_epoch,
            },
        )
    if crash_point == CRASH_PRE_COMMIT:
        steps.append({"step": "CRASH", "crash_point": crash_point})
        return _stop(f"crash:{crash_point}")
    if _has(ABORT):
        steps.append({"step": "REJECTED_STABLE"})
        return _stop("rejected_stable")
    if not _has(COMMIT):
        if epoch_at_commit > intent.authorized_consent_epoch:
            _append(ABORT, {"reason": RC_CONSENT_REVOKED_BEFORE_COMMIT})
            return _stop("aborted")
        _append(
            COMMIT,
            {
                "row_version": 1,
                "consent_epoch_at_commit": epoch_at_commit,
                "payload_digest_sha256": intent.payload_digest_sha256,
            },
        )
    # Materialize the clinical row from journal authority (idempotent).
    if stores.row_version(op) is None:
        commit_payload = next(entry.payload for entry in journal.entries if entry.kind == COMMIT)
        if stores.write_row(op, int(commit_payload["row_version"])):
            counts["row_writes"] += 1
            steps.append({"step": "ROW_WRITE", "operation_id": op})
    if crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
        steps.append({"step": "CRASH", "crash_point": crash_point})
        return _stop(f"crash:{crash_point}")
    if not _has(OUTBOX_RECORD):
        _append(OUTBOX_RECORD, {})
    # WAL-style replay: an effect journaled write-ahead but interrupted by the
    # mid_effect crash (effect-ack lost) is materialized into the durable store
    # exactly once during recovery before any new delivery is processed.
    if _effect_digests() and stores.effect_digest(op) is None:
        digest = sorted(_effect_digests())[0]
        if stores.apply_effect(op, digest):
            counts["effect_applications"] += 1
            steps.append({"step": "EFFECT_REPLAY", "operation_id": op})
    first_attempt = True
    for attempt in schedule:
        if crash_point == CRASH_PRE_OUTBOX_DELIVERY and first_attempt:
            steps.append({"step": "CRASH", "crash_point": crash_point})
            return _stop(f"crash:{crash_point}")
        first_attempt = False
        counts["deliveries_observed"] += 1
        if _effect_digests():
            counts["deliveries_deduped"] += 1
            steps.append({"step": "DELIVERY", "attempt": attempt, "result": "deduped_by_journal"})
            continue
        digest = _effect_digest(op)
        _append(EFFECT_APPLIED, {"attempt": attempt, "effect_receipt_digest": digest})
        if crash_point == CRASH_MID_EFFECT:
            steps.append({"step": "CRASH", "crash_point": crash_point})
            return _stop(f"crash:{crash_point}")
        if stores.apply_effect(op, digest):
            counts["effect_applications"] += 1
            steps.append({"step": "EFFECT_APPLY", "operation_id": op})
    steps.append({"step": "COMPLETED"})
    return _stop("completed")


# ---------------------------------------------------------------------------
# Recoverable-outcome function (pure adjudication, fail closed)
# ---------------------------------------------------------------------------


def _indeterminate(reason_code: str, **details: Any) -> RecoveryOutcome:
    return RecoveryOutcome(
        outcome=VERDICT_INDETERMINATE, reason_code=reason_code, retriable=False, details=details
    )


def _rejected(reason_code: str, retriable: bool, **details: Any) -> RecoveryOutcome:
    return RecoveryOutcome(
        outcome=VERDICT_REJECTED, reason_code=reason_code, retriable=retriable, details=details
    )


def _committed(reason_code: str, **details: Any) -> RecoveryOutcome:
    return RecoveryOutcome(
        outcome=VERDICT_COMMITTED, reason_code=reason_code, retriable=False, details=details
    )


def recoverable_outcome(journal: SafetyJournal, intent: WriteIntent) -> RecoveryOutcome:
    """Fold the journal into exactly one recoverable verdict (fail closed).

    Never raises: malformed input, corrupt chains, semantic contradictions and
    unexpected internal errors all map to ``INDETERMINATE`` with a stable
    reason code; only durable proof of non-commit yields ``REJECTED``.
    """

    try:
        intent_issues = _intent_issues(intent)
        if intent_issues:
            return _indeterminate(RC_MALFORMED_WRITE_INTENT, invalid_fields=sorted(intent_issues))
        if len(journal) == 0:
            # Nothing durable anywhere: the known empty picture is a retriable
            # non-commit (the same operation ID may re-run), not a corruption.
            return _rejected(
                RC_NOT_COMMITTED_NO_DURABLE_EVIDENCE, True, operation_id=intent.operation_id
            )
        defects = verify_journal(journal, intent.operation_id)
        if defects:
            return _indeterminate(RC_JOURNAL_CORRUPT, defects=list(defects))
        entries = journal.entries
        first = entries[0]
        if first.kind != INTENT:
            return _indeterminate(RC_INTENT_NOT_FIRST, seq=first.seq, kind=first.kind)
        if (
            first.payload.get("payload_digest_sha256") != intent.payload_digest_sha256
            or first.payload.get("authorized_consent_epoch") != intent.authorized_consent_epoch
        ):
            return _indeterminate(
                RC_JOURNAL_INTENT_MISMATCH, seq=first.seq, operation_id=intent.operation_id
            )
        seen_commit = False
        seen_abort = False
        effect_digests: set[str] = set()
        for entry in entries[1:]:
            kind = entry.kind
            if kind == COMMIT:
                if seen_commit or seen_abort:
                    return _indeterminate(
                        RC_DUPLICATE_COMMIT_RECORD
                        if seen_commit
                        else RC_ABORT_COMMIT_CONTRADICTION,
                        seq=entry.seq,
                    )
                payload = entry.payload
                if (
                    not _valid_int(payload.get("row_version"), minimum=1)
                    or not _valid_int(payload.get("consent_epoch_at_commit"))
                    or payload.get("payload_digest_sha256") != intent.payload_digest_sha256
                ):
                    return _indeterminate(RC_COMMIT_PAYLOAD_MALFORMED, seq=entry.seq)
                if payload["consent_epoch_at_commit"] > intent.authorized_consent_epoch:
                    return _rejected(
                        RC_FORBIDDEN_WRITE_POST_REVOCATION,
                        False,
                        seq=entry.seq,
                        authorized_consent_epoch=intent.authorized_consent_epoch,
                        consent_epoch_at_commit=payload["consent_epoch_at_commit"],
                    )
                seen_commit = True
            elif kind == ABORT:
                if seen_commit or seen_abort:
                    return _indeterminate(RC_ABORT_COMMIT_CONTRADICTION, seq=entry.seq)
                seen_abort = True
            elif kind == OUTBOX_RECORD:
                if not seen_commit or seen_abort:
                    return _indeterminate(RC_OUTBOX_WITHOUT_COMMIT, seq=entry.seq)
            elif kind == EFFECT_APPLIED:
                if not seen_commit or seen_abort:
                    return _indeterminate(RC_EFFECT_WITHOUT_COMMIT, seq=entry.seq)
                digest = entry.payload.get("effect_receipt_digest")
                if not _valid_sha256(digest):
                    return _indeterminate(RC_COMMIT_PAYLOAD_MALFORMED, seq=entry.seq)
                if effect_digests and digest not in effect_digests:
                    return _indeterminate(
                        RC_DUPLICATE_EFFECT_DIVERGENCE,
                        seq=entry.seq,
                        distinct_effect_digests=sorted(effect_digests | {digest}),
                    )
                effect_digests.add(digest)
        if seen_abort:
            return _rejected(
                RC_CONSENT_REVOKED_BEFORE_COMMIT, False, operation_id=intent.operation_id
            )
        if seen_commit:
            if effect_digests:
                return _committed(
                    RC_COMMITTED_EFFECT_APPLIED,
                    operation_id=intent.operation_id,
                    effect_receipt_digest=sorted(effect_digests)[0],
                )
            return _committed(RC_COMMITTED_PENDING_DELIVERY, operation_id=intent.operation_id)
        return _rejected(
            RC_NOT_COMMITTED_NO_DURABLE_EVIDENCE, True, operation_id=intent.operation_id
        )
    except Exception as exc:  # noqa: BLE001 - fail-closed adjudication boundary
        return _indeterminate(RC_INTERNAL_CANDIDATE_ERROR, error_class=type(exc).__name__)


# ---------------------------------------------------------------------------
# Corruption injection (fixture helper: interior tampering vs legal prefix)
# ---------------------------------------------------------------------------


CORRUPTION_MODES: Final[tuple[str, ...]] = (
    "flip_payload",
    "flip_digest",
    "drop_interior_entry",
    "unknown_kind",
)


def _rechain(entries: Sequence[JournalEntry], start: int) -> tuple[JournalEntry, ...]:
    """Rebuild prev/digest fields from ``start`` onward (chain-consistent tail)."""

    out: list[JournalEntry] = list(entries)
    prev = out[start - 1].entry_digest if start > 0 else GENESIS_PREV_DIGEST
    for index in range(start, len(out)):
        entry = dataclasses.replace(out[index], prev_entry_digest=prev, entry_digest="")
        entry = dataclasses.replace(entry, entry_digest=entry.compute_digest())
        out[index] = entry
        prev = entry.entry_digest
    return tuple(out)


def corrupt_journal(journal: SafetyJournal, mode: str, entry_index: int) -> SafetyJournal:
    """Return a tampered copy of ``journal`` (fixtures for fail-closed tests).

    ``flip_payload`` mutates an entry body without updating its digest;
    ``flip_digest`` forges the stored digest; ``drop_interior_entry`` removes a
    non-last entry (dropping the LAST entry is a legal prefix — a crash
    window, not corruption); ``unknown_kind`` rewrites a kind to an
    unregistered value and rechains the tail so only the semantic check can
    catch it. Raises :class:`CandidateError` on a malformed corruption spec.
    """

    if mode not in CORRUPTION_MODES:
        raise CandidateError(RC_CORRUPTION_SPEC_MALFORMED, f"mode {mode!r}")
    if not _valid_int(entry_index) or entry_index >= len(journal):
        raise CandidateError(RC_CORRUPTION_SPEC_MALFORMED, f"entry_index {entry_index!r}")
    entries = journal.entries
    target = entries[entry_index]
    if mode == "flip_payload":
        payload = dict(target.payload)
        payload["tampered"] = True
        tampered = dataclasses.replace(target, payload=payload)
        return SafetyJournal(entries[:entry_index] + (tampered,) + entries[entry_index + 1 :])
    if mode == "flip_digest":
        forged = dataclasses.replace(
            target, entry_digest=_synthetic_digest("tamper:" + str(target.seq))
        )
        return SafetyJournal(entries[:entry_index] + (forged,) + entries[entry_index + 1 :])
    if mode == "drop_interior_entry":
        if entry_index == len(entries) - 1:
            raise CandidateError(
                RC_CORRUPTION_SPEC_MALFORMED,
                "dropping the last entry is a legal prefix (crash window), not corruption",
            )
        return SafetyJournal(entries[:entry_index] + entries[entry_index + 1 :])
    tampered = dataclasses.replace(target, kind="GARBAGE_KIND")
    return SafetyJournal(
        _rechain(entries[:entry_index] + (tampered,) + entries[entry_index + 1 :], entry_index)
    )


# ---------------------------------------------------------------------------
# Mechanism-isolation ablation: journal-less execution (arm-B0 failure mode)
# ---------------------------------------------------------------------------


def ablation_no_journal_execute(
    intent: WriteIntent,
    *,
    crash_point: str = CRASH_NONE,
    delivery_schedule: Sequence[int] = (),
    stores: DurableStores | None = None,
    consent_epoch_at_commit: int | None = None,
) -> dict[str, Any]:
    """Execute without a decision lineage (journal removed).

    The DB row is written inside a simulated atomic transaction and every
    broker delivery applies the side effect fire-and-forget (no dedup, no
    write-ahead record). Because no durable lineage exists, a retry after a
    crash window cannot adjudicate anything (``recoverable_outcome_available``
    is ``False``) — the returned report carries counts only; JSON-serializable.
    """

    intent_issues = _intent_issues(intent)
    if intent_issues:
        raise CandidateError(RC_MALFORMED_WRITE_INTENT, f"invalid fields: {sorted(intent_issues)}")
    if crash_point not in CRASH_POINTS:
        raise CandidateError(RC_CRASH_POINT_UNKNOWN, f"crash_point {crash_point!r}")
    schedule = _validated_schedule(delivery_schedule)
    epoch_at_commit = _validated_epoch(consent_epoch_at_commit, intent)
    stores = stores if stores is not None else DurableStores()
    op = intent.operation_id
    report: dict[str, Any] = {
        "ablation_id": ABLATION_ID,
        "crash_point": crash_point,
        "row_write_attempts": 0,
        "effect_applications": 0,
        "deliveries_observed": 0,
        "recoverable_outcome_available": False,
    }
    if crash_point == CRASH_PRE_COMMIT:
        return report
    if epoch_at_commit > intent.authorized_consent_epoch:
        report["aborted"] = RC_CONSENT_REVOKED_BEFORE_COMMIT
        return report
    # The row write is re-attempted by every episode; the durable row itself is
    # keyed by the operation ID, so the count shows retries, not duplicates.
    stores.write_row(op, 1)
    report["row_write_attempts"] = 1
    if crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
        return report
    first_attempt = True
    for _attempt in schedule:
        if crash_point == CRASH_PRE_OUTBOX_DELIVERY and first_attempt:
            break
        first_attempt = False
        report["deliveries_observed"] = int(report["deliveries_observed"]) + 1
        # Fire-and-forget consumer: every delivery applies the effect.
        stores.effects[f"{op}#{report['deliveries_observed']}"] = _effect_digest(op)
        stores.effect_apply_count += 1
        report["effect_applications"] = int(report["effect_applications"]) + 1
        if crash_point == CRASH_MID_EFFECT:
            break
    return report


# ---------------------------------------------------------------------------
# Mechanism description
# ---------------------------------------------------------------------------


def describe_mechanism() -> dict[str, Any]:
    """JSON-serializable statement of the mechanism and its guarantees."""

    return {
        "candidate_id": CANDIDATE_ID,
        "ablation_id": ABLATION_ID,
        "version": CANDIDATE_VERSION,
        "journal_version": JOURNAL_VERSION,
        "mechanism": "hash-chained per-operation recoverable safety journal",
        "enforcement": {
            "write_ahead_effect_record": True,
            "hash_chained_lineage": True,
            "idempotent_retry_by_operation_id": True,
            "consent_recheck_at_commit": True,
            "fail_closed_adjudication": True,
        },
        "verdicts": (VERDICT_COMMITTED, VERDICT_REJECTED, VERDICT_INDETERMINATE),
        "crash_points": list(CRASH_POINTS),
        "guarantees": [
            "a committed clinical row always carries a journal COMMIT record",
            "the side effect is journaled before it is applied (write-ahead)",
            "duplicate deliveries dedupe against the journaled effect record",
            "a corrupted journal never adjudicates to COMMITTED or a safe REJECTED",
            "retry after any crash window resumes the episode exactly once",
        ],
        "non_guarantees": [
            "no empirical rates, latency or cost numbers are claimed here",
            "no erasure of effects already applied before a revocation",
            "no claim that B1/B2 baselines cannot match these invariants (falsifiable)",
        ],
    }


# ---------------------------------------------------------------------------
# Harness adapter: run_candidate(case, ctx) -> Outcome
# ---------------------------------------------------------------------------

CASE_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"case_id", "operation_id", "authorized_consent_epoch", "delivery_schedule"}
)
CASE_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset(
    {"consent_epoch_at_commit", "crash_point", "corrupt_journal"}
)
CASE_KEYS: Final[frozenset[str]] = CASE_REQUIRED_KEYS | CASE_OPTIONAL_KEYS
CORRUPTION_KEYS: Final[frozenset[str]] = frozenset({"mode", "entry_index"})


def _validated_case(case: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(case, Mapping):
        raise CandidateError(RC_CASE_NOT_AN_OBJECT, f"case must be a mapping, got {type(case)}")
    unknown = sorted(set(map(str, case)) - CASE_KEYS)
    if unknown:
        raise CandidateError(RC_CASE_UNKNOWN_FIELD, f"unknown case keys: {unknown}")
    for field in sorted(CASE_REQUIRED_KEYS):
        if field not in case:
            raise CandidateError(RC_CASE_MISSING_FIELD, f"missing case field: {field}")
    if not _valid_label(case["case_id"]) or not _valid_label(case["operation_id"]):
        raise CandidateError(RC_CASE_BAD_FIELD, "case_id/operation_id must be short label strings")
    if not _valid_int(case["authorized_consent_epoch"]):
        raise CandidateError(RC_CASE_BAD_FIELD, "authorized_consent_epoch must be an int >= 0")
    schedule = case["delivery_schedule"]
    if not isinstance(schedule, list):
        raise CandidateError(RC_CASE_BAD_FIELD, "delivery_schedule must be a list")
    for attempt in schedule:
        if not _valid_int(attempt, minimum=1):
            raise CandidateError(RC_CASE_BAD_FIELD, "delivery_schedule entries must be ints >= 1")
    crash_point = case.get("crash_point", CRASH_NONE)
    if crash_point not in CRASH_POINTS:
        raise CandidateError(RC_CASE_BAD_FIELD, f"crash_point {crash_point!r} unknown")
    if "consent_epoch_at_commit" in case and not _valid_int(case["consent_epoch_at_commit"]):
        raise CandidateError(RC_CASE_BAD_FIELD, "consent_epoch_at_commit must be an int >= 0")
    corruption = case.get("corrupt_journal")
    if corruption is not None:
        if not isinstance(corruption, Mapping) or set(map(str, corruption)) - CORRUPTION_KEYS:
            raise CandidateError(
                RC_CORRUPTION_SPEC_MALFORMED,
                "corrupt_journal must be an object with mode/entry_index",
            )
        if corruption.get("mode") not in CORRUPTION_MODES or not _valid_int(
            corruption.get("entry_index")
        ):
            raise CandidateError(
                RC_CORRUPTION_SPEC_MALFORMED, "corrupt_journal mode/entry_index invalid"
            )
    return dict(case)


def run_candidate(case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Run one full crash/recovery/adjudication episode for the shared harness.

    Episode: execute (with the case's crash window) -> inject declared journal
    corruption, if any -> resume (recovery re-runs the same operation ID on a
    healthy machine, replaying the delivery schedule) -> adjudicate the final
    journal with :func:`recoverable_outcome`. Pair-level mapping: COMMITTED ->
    ADMIT and REJECTED -> REJECT (both counted outcomes); INDETERMINATE
    (including corruption-refused recovery) -> INDETERMINATE (never counted).
    Malformed cases fail closed with ``EXECUTION_ERROR`` and a stable reason
    code. No empirical claim is attached.
    """

    del ctx  # no hidden randomness: the case fully determines the run
    try:
        spec = _validated_case(case)
    except CandidateError as exc:
        return Outcome("EXECUTION_ERROR", detail=f"{exc.reason_code}: {exc.detail}")
    intent = WriteIntent(
        operation_id=str(spec["operation_id"]),
        tenant_id="synthetic-tenant",
        principal_id="synthetic-actor",
        purpose="self_care",
        authorized_consent_epoch=int(spec["authorized_consent_epoch"]),
        payload_digest_sha256=_synthetic_digest("payload:" + str(spec["operation_id"])),
        issued_logical_time=10,
    )
    try:
        first = execute_operation(
            intent,
            crash_point=str(spec.get("crash_point", CRASH_NONE)),
            delivery_schedule=tuple(spec["delivery_schedule"]),
            consent_epoch_at_commit=spec.get("consent_epoch_at_commit"),
        )
        journal = first.journal
        corruption = spec.get("corrupt_journal")
        if corruption is not None:
            journal = corrupt_journal(
                journal, str(corruption["mode"]), int(corruption["entry_index"])
            )
        # Recovery: the operation re-runs under the same immutable operation ID.
        try:
            resumed = execute_operation(
                intent,
                delivery_schedule=tuple(spec["delivery_schedule"]),
                journal=journal,
            )
        except CandidateError as exc:
            if exc.reason_code != RC_JOURNAL_CORRUPT:
                raise
            # Corrupted lineage: recovery is refused, fail closed — the
            # adjudication is INDETERMINATE, never a silent success and never
            # a coerced safe rejection (DSN-CASE-06).
            verdict = _indeterminate(RC_JOURNAL_CORRUPT, operation_id=intent.operation_id)
            return Outcome(
                observed_outcome="INDETERMINATE",
                counted_as_success=False,
                detail=json.dumps(
                    {
                        "candidate_id": CANDIDATE_ID,
                        "version": CANDIDATE_VERSION,
                        "case_id": str(spec["case_id"]),
                        "operation_id": intent.operation_id,
                        "crash_point": first.crash_point,
                        "verdict": verdict.to_dict(),
                        "resume": {"resumed": False, "refused": RC_JOURNAL_CORRUPT},
                        "journal_length": len(journal),
                        "design_only": "no empirical claims; mechanism + executable invariants only",
                    },
                    sort_keys=True,
                ),
            )
        verdict = recoverable_outcome(resumed.journal, intent)
    except CandidateError as exc:
        return Outcome("EXECUTION_ERROR", detail=f"{exc.reason_code}: {exc.detail}")
    except Exception as exc:  # noqa: BLE001 - fail-closed adapter boundary
        return Outcome(
            "EXECUTION_ERROR",
            detail=f"{RC_INTERNAL_CANDIDATE_ERROR}: {type(exc).__name__}",
        )
    mapping = {
        VERDICT_COMMITTED: ("ADMIT", True),
        VERDICT_REJECTED: ("REJECT", True),
        VERDICT_INDETERMINATE: ("INDETERMINATE", False),
    }
    observed, counted = mapping[verdict.outcome]
    detail = {
        "candidate_id": CANDIDATE_ID,
        "version": CANDIDATE_VERSION,
        "case_id": str(spec["case_id"]),
        "operation_id": intent.operation_id,
        "crash_point": first.crash_point,
        "verdict": verdict.to_dict(),
        "resume": {
            "resumed": resumed.resumed,
            "stopped_at": resumed.stopped_at,
            "row_writes": resumed.row_writes,
            "effect_applications": resumed.effect_applications,
            "deliveries_observed": resumed.deliveries_observed,
            "deliveries_deduped": resumed.deliveries_deduped,
        },
        "journal_length": len(resumed.journal),
        "design_only": "no empirical claims; mechanism + executable invariants only",
    }
    return Outcome(
        observed_outcome=observed,
        counted_as_success=counted,
        detail=json.dumps(detail, sort_keys=True),
    )
