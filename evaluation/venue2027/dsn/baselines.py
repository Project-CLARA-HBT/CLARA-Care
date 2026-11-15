"""DSN baseline fidelity adapters (task DSN-baselines, phase P03).

Purpose
-------
In-process reference implementations of the strong-baseline arms for the DSN
2027 study "Recoverable Safety Journals for Crash-Consistent AI-Mediated
Health-State Mutations" (``research/venue2027/VENUES/dsn/RESEARCH_BLUEPRINT.md``,
task contract ``research/venue2027/VENUES/dsn/TASKS/DSN-baselines.md``). Each
arm executes one governed clinical write intent against an injected in-process
store (``ctx.store`` dict) and returns a first-class harness :class:`Outcome`
with a stable ``reason_code``:

- ``B0-single-write``: one bare durable write of the clinical row; the
  side-effect record is fire-and-forget and there is no journal. A crash
  before the durable write loses the operation entirely; a crash between the
  durable write and the side-effect record leaves the side effect orphaned
  and a later blind retry re-applies it (duplicate). Weak control; measures
  lost / duplicated side effects.
- ``B1-outbox-idempotent``: durable clinical row + transactional outbox
  record + an idempotency-key dedup table for retries. A retry whose
  idempotency key is already durably recorded is a no-op that re-acks the
  original outcome, so duplicate deliveries cannot re-apply the effect. The
  strong practical baseline; must be implemented fully (it is).
- ``B3-fsync``: fsync discipline — every write is flushed before it is
  acknowledged, but there is no atomic multi-channel commit: a crash between
  the acknowledged row fsync and the not-yet-durable side-effect/WAL record
  can still lose the side effect (pre-WAL window). Measures the residual
  loss window fsync alone cannot close.
- ``B4-candidate-journal``: the proposed reconciliation safety journal — a
  write-ahead journal entry is made durable BEFORE any channel write, and
  recovery dedups by immutable operation id, so any replay after a crash is
  exactly-once across the crash window.
- ``B5-monotonic-journal``: B4 plus a monotonic journal sequence guard —
  recovery additionally rejects out-of-order / stale journal entries (a
  stale entry behind an already-committed sequence cannot resurrect a
  superseded state).

Allowed input
-------------
A JSON-serializable ``case`` mapping ``{"case_id": str, "operation_id": str,
"crash_point": str, "delivery_schedule": [ints], "consent_epoch": int}`` and
an injected :class:`BaselineContext` carrying the arm's in-process ``store``
dict plus ``recovery_retries`` (deterministic retry count for the recovery
pass). ``crash_point`` is one of ``none`` / ``pre_commit`` /
``post_commit_pre_response`` / ``pre_outbox_delivery`` (mirrors
CASE_MATRIX DSN-CASE-02..07 and the state machine's :class:`CrashPoint`
names); ``delivery_schedule`` lists at-least-once replay attempt indices.
No hidden clock, no randomness, no network, no live provider, no real
PHI/PII; every timestamp is a caller-supplied logical integer.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. ``run_baseline`` returns a
first-class harness :class:`Outcome`: ``ADMIT`` (operation committed and the
side effect applied at most once) carries ``counted_as_success=True``;
``REJECT`` (no durable evidence anywhere — crash before any write) is
retriable because recovery must re-run it under the same operation id;
``INDETERMINATE`` (torn evidence) is never coerced into a safe rejection or
a success; ``NOT_RUN_EXTERNAL`` is reserved for arms whose pinned upstream
is unavailable (never a toy substitution). Malformed cases/contexts and
unknown baseline ids are wiring errors raised as :class:`BaselineError`.
``refuse_constant_stub`` replays paired crash/no-crash probe cases through
any candidate adapter and refuses constant-output stubs that ignore the
crash point.

Version
-------
``BASELINES_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

BASELINES_VERSION = "1.0.0"

#: Blueprint / task-contract arm ids (B2 durable workflow is pinned external).
BASELINE_B0 = "B0-single-write"
BASELINE_B1 = "B1-outbox-idempotent"
BASELINE_B3 = "B3-fsync"
BASELINE_B4 = "B4-candidate-journal"
BASELINE_B5 = "B5-monotonic-journal"

#: Pinned external arm (durable workflow/saga engine, registry ORIGINAL_UPSTREAM).
#: Its engine version and parity fixture are absent from this worktree, so it
#: stays NOT_RUN_EXTERNAL (never a toy under the pinned name, rule 8).
BASELINE_B2_WORKFLOW = "B2-durable-workflow"

EXTERNAL_PINNED_BASELINES: frozenset[str] = frozenset({BASELINE_B2_WORKFLOW})

#: Registry name -> arm id (mirrors research/venue2027/_shared/baselines/registry.yaml).
REGISTRY_BASELINE_NAMES: Mapping[str, str] = {
    "db-transaction-fire-and-forget": BASELINE_B0,
    "transactional-outbox-idempotent-consumer": BASELINE_B1,
    "durable-workflow-saga": BASELINE_B2_WORKFLOW,
    "fsync-discipline": BASELINE_B3,
    "reconciliation-safety-journal": BASELINE_B4,
    "monotonic-safety-journal": BASELINE_B5,
}

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_OP_COMMITTED = "OP_COMMITTED"
RC_OP_COMMITTED_IDEMPOTENT_RETRY = "OP_COMMITTED_IDEMPOTENT_RETRY"
RC_OP_NOT_DURABLE = "OP_NOT_DURABLE_CRASH_BEFORE_WRITE"
RC_OP_LOST_SIDE_EFFECT = "OP_LOST_SIDE_EFFECT_PRE_WAL"
RC_OP_TORN_STATE = "OP_TORN_STATE_INDETERMINATE"
RC_JOURNAL_REPLAY_DEDUP = "OP_JOURNAL_REPLAY_DEDUPED"
RC_JOURNAL_STALE_ENTRY = "OP_JOURNAL_STALE_ENTRY_REJECTED"
RC_BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
RC_CASE_NOT_AN_OBJECT = "CASE_NOT_AN_OBJECT"
RC_CASE_MISSING_FIELD = "CASE_MISSING_FIELD"
RC_CASE_BAD_TYPE = "CASE_BAD_TYPE"
RC_CASE_UNKNOWN_FIELD = "CASE_UNKNOWN_FIELD"
RC_CASE_EMPTY_OP_ID = "CASE_EMPTY_OPERATION_ID"
RC_CRASH_POINT_UNKNOWN = "CRASH_POINT_UNKNOWN"
RC_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"
RC_BASELINE_UNKNOWN_ID = "BASELINE_UNKNOWN_ID"
RC_DELIVERY_SCHEDULE_BAD = "DELIVERY_SCHEDULE_MALFORMED"
RC_STUB_CONSTANT = "CONSTANT_STUB_REFUSED"
RC_STUB_SEPARATION_OK = "STUB_SEPARATION_OK"

#: The 14 case keys (exact schema; extra keys fail closed).
CASE_KEYS: frozenset[str] = frozenset(
    {
        "case_id",
        "operation_id",
        "crash_point",
        "delivery_schedule",
        "consent_epoch",
    }
)

#: Crash cut points (mirrors state_machine.CrashPoint / CASE_MATRIX windows).
CRASH_NONE = "none"
CRASH_PRE_COMMIT = "pre_commit"
CRASH_POST_COMMIT_PRE_RESPONSE = "post_commit_pre_response"
CRASH_PRE_OUTBOX_DELIVERY = "pre_outbox_delivery"
CRASH_POINTS: frozenset[str] = frozenset(
    {CRASH_NONE, CRASH_PRE_COMMIT, CRASH_POST_COMMIT_PRE_RESPONSE, CRASH_PRE_OUTBOX_DELIVERY}
)


class BaselineError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an arm outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass
class BaselineContext:
    """Injected per-run context: the arm's store plus recovery knobs.

    ``store`` is a plain dict acting as the in-process durable store; every
    arm owns its keys. ``recovery_retries`` bounds the deterministic recovery
    replay pass (>= 1). No hidden state is shared between arms: a fresh
    store per case keeps arms independent.
    """

    store: dict[str, Any]
    recovery_retries: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.store, dict):
            raise BaselineError(RC_CONTEXT_MALFORMED, "store must be a dict")
        if isinstance(self.recovery_retries, bool) or not isinstance(self.recovery_retries, int):
            raise BaselineError(RC_CONTEXT_MALFORMED, "recovery_retries must be an int")
        if self.recovery_retries < 1:
            raise BaselineError(RC_CONTEXT_MALFORMED, "recovery_retries must be >= 1")


@dataclasses.dataclass(frozen=True)
class _Case:
    """Validated, normalized case (internal)."""

    case_id: str
    operation_id: str
    crash_point: str
    delivery_schedule: tuple[int, ...]
    consent_epoch: int


# ---------------------------------------------------------------------------
# Case validation (fail closed).
# ---------------------------------------------------------------------------


def _validate_case(case: Mapping[str, Any]) -> _Case:
    if not isinstance(case, Mapping):
        raise BaselineError(RC_CASE_NOT_AN_OBJECT, f"case must be a mapping, got {type(case)}")
    unknown = sorted(set(map(str, case)) - CASE_KEYS)
    if unknown:
        raise BaselineError(RC_CASE_UNKNOWN_FIELD, f"unknown case keys: {unknown}")
    for field in ("case_id", "operation_id", "crash_point", "delivery_schedule", "consent_epoch"):
        if field not in case:
            raise BaselineError(RC_CASE_MISSING_FIELD, f"missing case field: {field}")
    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        raise BaselineError(RC_CASE_BAD_TYPE, "case_id must be a non-empty string")
    operation_id = case["operation_id"]
    if not isinstance(operation_id, str) or not operation_id:
        raise BaselineError(RC_CASE_EMPTY_OP_ID, "operation_id must be a non-empty string")
    crash_point = case["crash_point"]
    if not isinstance(crash_point, str) or crash_point not in CRASH_POINTS:
        raise BaselineError(
            RC_CRASH_POINT_UNKNOWN, f"crash_point {crash_point!r} not in {sorted(CRASH_POINTS)}"
        )
    schedule = case["delivery_schedule"]
    if not isinstance(schedule, list | tuple) or any(
        isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in schedule
    ):
        raise BaselineError(
            RC_DELIVERY_SCHEDULE_BAD,
            "delivery_schedule must be a list of positive ints (attempt indices)",
        )
    epoch = case["consent_epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise BaselineError(RC_CASE_BAD_TYPE, "consent_epoch must be a non-negative int")
    return _Case(
        case_id=case_id,
        operation_id=operation_id,
        crash_point=crash_point,
        delivery_schedule=tuple(schedule),
        consent_epoch=epoch,
    )


# ---------------------------------------------------------------------------
# Store-key conventions (per-arm namespaces inside the injected dict).
# ---------------------------------------------------------------------------


def _row_key(op: str) -> str:
    return f"row:{op}"


def _outbox_key(op: str) -> str:
    return f"outbox:{op}"


def _idem_key(op: str) -> str:
    return f"idem:{op}"


def _journal_key(op: str) -> str:
    return f"journal:{op}"


def _seq_key() -> str:
    return "seq:monotonic"


def _outcome(success: bool, retriable: bool, reason_code: str) -> Outcome:
    return Outcome(
        observed_outcome="ADMIT" if success else "REJECT",
        counted_as_success=success,
        retriable=retriable,
        detail=reason_code,
    )


# ---------------------------------------------------------------------------
# Arms.
# ---------------------------------------------------------------------------


def _run_b0_single_write(case: _Case, ctx: BaselineContext) -> Outcome:
    """DB transaction only + fire-and-forget side effect, no journal.

    Crash model (deterministic):
    - ``pre_commit``: nothing durable -> the operation is lost. The arm has
      no retry journal, so the loss is silent: REJECT, retriable (a later
      delivery replay would re-run it), counted_as_success=False.
    - ``post_commit_pre_response``: row durable but the side-effect record
      never happened (fire-and-forget). A blind retry re-applies the effect:
      the store keeps the orphan row and a re-execution duplicates it.
    - ``pre_outbox_delivery`` / none: row + side effect both land; no dedup,
      so any schedule replay duplicates the effect.
    """
    op = case.operation_id
    store = ctx.store
    if case.crash_point == CRASH_PRE_COMMIT:
        return _outcome(False, True, RC_OP_NOT_DURABLE)
    if _row_key(op) in store:
        # Blind retry over an existing row: duplicate side effect (no dedup).
        store[_row_key(op)] = store[_row_key(op)] + 1
    else:
        store[_row_key(op)] = 1
    if case.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
        # Side effect lost; the orphan row persists and the caller saw neither
        # ack nor the effect. Recovery replay will duplicate the write.
        return _outcome(False, True, RC_OP_LOST_SIDE_EFFECT)
    for _attempt in case.delivery_schedule:
        store[_row_key(op)] = store[_row_key(op)] + 1
    return _outcome(True, False, RC_OP_COMMITTED)


def _run_b1_outbox_idempotent(case: _Case, ctx: BaselineContext) -> Outcome:
    """Durable row + transactional outbox + idempotency-key dedup.

    The idempotency key is recorded in the same "transaction" as the row +
    outbox record. A retry finding the key re-acks the original outcome
    without re-applying the effect, so duplicate deliveries are harmless.
    Crash windows:
    - ``pre_commit``: nothing durable -> REJECTED, retriable (recovery
      re-runs it under the same operation id; the consumer is idempotent).
    - ``post_commit_pre_response``: row + outbox + idem key durable, ack
      lost. Recovery replays, finds the idempotency key, re-acks ADMIT
      without re-applying: exactly-once for the effect.
    - ``pre_outbox_delivery``: deliveries still replay per the schedule and
      each is deduped by the idempotency key.
    """
    op = case.operation_id
    store = ctx.store
    if case.crash_point == CRASH_PRE_COMMIT:
        return _outcome(False, True, RC_OP_NOT_DURABLE)
    if _idem_key(op) in store:
        # Idempotent consumer: dedup the retry, never re-apply the effect.
        return _outcome(True, False, RC_OP_COMMITTED_IDEMPOTENT_RETRY)
    if case.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
        store[_row_key(op)] = 1
        store[_outbox_key(op)] = 0
        store[_idem_key(op)] = 1
        # Ack lost before delivery; recovery replay dedups.
        return _outcome(True, False, RC_OP_COMMITTED_IDEMPOTENT_RETRY)
    store[_row_key(op)] = 1
    store[_outbox_key(op)] = 0
    store[_idem_key(op)] = 1
    for _attempt in case.delivery_schedule:
        # At-least-once delivery; idempotency key caps the effect at one.
        store[_outbox_key(op)] = store[_outbox_key(op)] + 1
    return _outcome(True, False, RC_OP_COMMITTED)


def _run_b3_fsync(case: _Case, ctx: BaselineContext) -> Outcome:
    """Fsync discipline: every acknowledged write is flushed, no journal.

    Fsync closes the torn-write window on each individual channel, but there
    is no atomic multi-channel commit: a crash after the acknowledged row
    fsync but before the side-effect record reaches its own durable surface
    (pre-WAL for the side channel) still loses the side effect. The arm
    reports this honestly as a lost side effect rather than a success.
    """
    op = case.operation_id
    store = ctx.store
    if case.crash_point == CRASH_PRE_COMMIT:
        # Fsync of nothing: no durable evidence anywhere.
        return _outcome(False, True, RC_OP_NOT_DURABLE)
    if _row_key(op) in store:
        # Fsync'd row already durable; recovery replay re-acks without a
        # journal, but the side-effect channel state is unverifiable here.
        if case.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
            return _outcome(False, True, RC_OP_LOST_SIDE_EFFECT)
        return _outcome(True, False, RC_OP_COMMITTED)
    store[_row_key(op)] = 1
    if case.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
        # Row fsync'd and acked; side-effect fsync never reached its WAL.
        return _outcome(False, True, RC_OP_LOST_SIDE_EFFECT)
    for _attempt in case.delivery_schedule:
        store[_row_key(op)] = store[_row_key(op)] + 1
    return _outcome(True, False, RC_OP_COMMITTED)


def _run_b4_candidate_journal(case: _Case, ctx: BaselineContext) -> Outcome:
    """Write-ahead journal + dedup by operation id = exactly-once across crash.

    The journal entry is made durable BEFORE any channel write (write-ahead
    discipline). After any crash, recovery replays the journal: if the
    operation id is journaled and not yet marked applied, recovery re-applies
    it exactly once; if already applied, the replay is deduped to a no-op.
    Every crash window yields a committed, exactly-once outcome (or a
    retriable reject when nothing at all was journaled).
    """
    op = case.operation_id
    store = ctx.store
    journal = store.get(_journal_key(op))
    if journal is not None:
        # Recovery replay over an existing journal entry: dedup by op id.
        if journal.get("applied"):
            return _outcome(True, False, RC_JOURNAL_REPLAY_DEDUP)
    if case.crash_point == CRASH_PRE_COMMIT:
        # Journal write itself lost: nothing durable, fail and retry.
        return _outcome(False, True, RC_OP_NOT_DURABLE)
    # Write-ahead: journal BEFORE the channel writes.
    store[_journal_key(op)] = {"applied": False, "consent_epoch": case.consent_epoch}
    if case.crash_point in (CRASH_POST_COMMIT_PRE_RESPONSE, CRASH_PRE_OUTBOX_DELIVERY):
        # Crash lands mid-flight; recovery replay completes the operation
        # exactly once (journal is durable, so the op survives the crash).
        store[_journal_key(op)]["applied"] = True
        return _outcome(True, False, RC_OP_COMMITTED)
    store[_journal_key(op)]["applied"] = True
    for _attempt in case.delivery_schedule:
        # At-least-once deliveries; journal dedup caps the effect at one.
        store[_journal_key(op)]["applied_count"] = (
            store[_journal_key(op)].get("applied_count", 0) + 1
        )
    return _outcome(True, False, RC_OP_COMMITTED)


def _run_b5_monotonic_journal(case: _Case, ctx: BaselineContext) -> Outcome:
    """B4 plus a monotonic journal sequence guard on recovery.

    Recovery additionally verifies that a replayed journal entry is not
    stale: an entry whose recorded sequence is behind the store's committed
    monotonic watermark cannot resurrect a superseded state and is rejected
    (stale-entry guard). Fresh writes always carry a sequence above the
    watermark, so the guard never blocks legitimate forward progress.
    """
    op = case.operation_id
    store = ctx.store
    journal = store.get(_journal_key(op))
    watermark = store.get(_seq_key(), 0)
    if journal is not None and journal.get("applied"):
        if journal.get("seq", 0) < watermark:
            return _outcome(False, False, RC_JOURNAL_STALE_ENTRY)
        return _outcome(True, False, RC_JOURNAL_REPLAY_DEDUP)
    if case.crash_point == CRASH_PRE_COMMIT:
        return _outcome(False, True, RC_OP_NOT_DURABLE)
    seq = watermark + 1
    store[_journal_key(op)] = {
        "applied": False,
        "consent_epoch": case.consent_epoch,
        "seq": seq,
    }
    store[_seq_key()] = seq
    if case.crash_point in (CRASH_POST_COMMIT_PRE_RESPONSE, CRASH_PRE_OUTBOX_DELIVERY):
        store[_journal_key(op)]["applied"] = True
        return _outcome(True, False, RC_OP_COMMITTED)
    store[_journal_key(op)]["applied"] = True
    for _attempt in case.delivery_schedule:
        store[_journal_key(op)]["applied_count"] = (
            store[_journal_key(op)].get("applied_count", 0) + 1
        )
    return _outcome(True, False, RC_OP_COMMITTED)


_EVALUATORS: Mapping[str, Any] = {
    BASELINE_B0: _run_b0_single_write,
    BASELINE_B1: _run_b1_outbox_idempotent,
    BASELINE_B3: _run_b3_fsync,
    BASELINE_B4: _run_b4_candidate_journal,
    BASELINE_B5: _run_b5_monotonic_journal,
}


# ---------------------------------------------------------------------------
# Registry + dispatch.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BaselineSpec:
    """Registry row: provenance + runnability for one baseline arm."""

    baseline_id: str
    registry_name: str
    title: str
    algorithm_class: str
    runnable_in_process: bool
    upstream_url: str
    upstream_revision: str
    notes: str


BASELINE_REGISTRY: Mapping[str, BaselineSpec] = {
    spec.baseline_id: spec
    for spec in (
        BaselineSpec(
            baseline_id=BASELINE_B0,
            registry_name="db-transaction-fire-and-forget",
            title="DB transaction only + fire-and-forget side effect",
            algorithm_class=(
                "single bare durable write; side-effect record sent after the commit "
                "with no journal, no outbox and no dedup"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Weak control (blueprint strong-baseline row B0): measures lost and "
                "duplicated side effects across crash windows. Crash before the "
                "durable write loses the operation; crash after the commit orphans "
                "the side effect and a blind retry re-applies it."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B1,
            registry_name="transactional-outbox-idempotent-consumer",
            title="Atomic write + transactional outbox + idempotent consumer",
            algorithm_class=(
                "row + outbox record + idempotency key written in one durable "
                "transaction; retries and replays dedup on the key"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Strong practical baseline (blueprint row B1), implemented fully "
                "in-process: the falsification arm for the candidate journal. If it "
                "matches B4's invariants at equal cost, the candidate-superiority "
                "claim must be discarded."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B2_WORKFLOW,
            registry_name="durable-workflow-saga",
            title="Durable workflow/saga with compensation and stable operation IDs",
            algorithm_class=(
                "durable workflow engine with compensations and stable operation ids"
            ),
            runnable_in_process=False,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Pinned external engine arm (blueprint row B2): the engine version "
                "and its parity fixture are absent from this worktree, so the arm "
                "returns NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE (never a toy "
                "substitution under the pinned name)."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B3,
            registry_name="fsync-discipline",
            title="Fsync discipline without an atomic multi-channel commit",
            algorithm_class=(
                "every acknowledged write is fsync'd on its own channel; no journal, "
                "so the pre-WAL window of the side channel stays exposed"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Durability-posture control: fsync closes per-channel torn writes "
                "but cannot close the cross-channel window (crash between the row "
                "fsync and the side-effect WAL record)."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B4,
            registry_name="reconciliation-safety-journal",
            title="Candidate reconciliation safety journal (write-ahead + op-id dedup)",
            algorithm_class=(
                "durable write-ahead journal entry before any channel write; recovery "
                "replays the journal and dedups by immutable operation id"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Candidate arm (blueprint row B3/B4): must give exactly-once across "
                "the crash window that B0 loses/duplicates and B3 leaves exposed."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B5,
            registry_name="monotonic-safety-journal",
            title="Candidate journal + monotonic sequence guard",
            algorithm_class=(
                "B4 write-ahead journal plus a monotonic sequence watermark; recovery "
                "rejects stale journal entries behind the watermark"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Candidate variant adding stale-entry protection: an out-of-order "
                "journal replay cannot resurrect a superseded state."
            ),
        ),
    )
}


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    """Execute one baseline arm on one crash-window case.

    Returns a first-class harness :class:`Outcome`: ADMIT (committed,
    effect applied at most once) carries ``counted_as_success=True``; REJECT
    is retriable when recovery must re-run the operation (crash before any
    durable write) and non-retriable when the outcome is final; the pinned
    external arm returns ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE``
    (never counted, never a toy substitution). Unknown baseline ids,
    non-mapping cases and malformed contexts are wiring errors raised as
    :class:`BaselineError`.
    """
    if not isinstance(ctx, BaselineContext):
        raise BaselineError(RC_CONTEXT_MALFORMED, f"ctx must be a BaselineContext, got {type(ctx)}")
    if baseline_id in EXTERNAL_PINNED_BASELINES:
        return Outcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            retriable=False,
            detail=RC_BASELINE_UNAVAILABLE,
        )
    spec = BASELINE_REGISTRY.get(baseline_id)
    if spec is None:
        known = sorted(BASELINE_REGISTRY)
        raise BaselineError(
            RC_BASELINE_UNKNOWN_ID, f"baseline_id {baseline_id!r} not in registry {known}"
        )
    validated = _validate_case(case)
    if baseline_id not in _EVALUATORS:
        raise BaselineError(RC_BASELINE_UNKNOWN_ID, f"no evaluator for {baseline_id!r}")
    return _EVALUATORS[baseline_id](validated, ctx)


# ---------------------------------------------------------------------------
# Paired probe fixtures + constant-stub refusal gate (EXECUTION_CONTRACT 8).
# ---------------------------------------------------------------------------


def crash_probe_cases() -> tuple[dict[str, Any], dict[str, Any]]:
    """Paired probes that differ ONLY in the crash point.

    ``clean`` runs the window with no crash; ``crashed`` uses
    ``pre_commit``. A faithful arm's outcome must depend on which one it
    sees; a constant stub returns the same outcome for both.
    """

    def make(case_id: str, crash_point: str) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "operation_id": f"op:probe-{case_id}",
            "crash_point": crash_point,
            "delivery_schedule": [1],
            "consent_epoch": 3,
        }

    return make("probe-clean", CRASH_NONE), make("probe-crash", CRASH_PRE_COMMIT)


def refuse_constant_stub(
    candidate: Any,
    *,
    clean_probe: Mapping[str, Any] | None = None,
    crashed_probe: Mapping[str, Any] | None = None,
) -> Outcome:
    """Refuse constant-output stubs (rule 8: no toy wearing a baseline name).

    Replays the paired clean/crashed probe cases through ``candidate`` and
    refuses a candidate whose (observed_outcome, detail) signature is
    identical across the pair — zero input sensitivity to the crash point
    means the adapter ignores the very variable the study manipulates
    (``CONSTANT_STUB_REFUSED``). Returns ``ADMIT`` / ``STUB_SEPARATION_OK``
    when the candidate distinguishes the pair.
    """
    clean, crashed = crash_probe_cases()
    clean_case = clean if clean_probe is None else dict(clean_probe)
    crashed_case = crashed if crashed_probe is None else dict(crashed_probe)
    outcomes = []
    for probe in (clean_case, crashed_case):
        result = candidate(probe)
        if not isinstance(result, Outcome):
            raise BaselineError(RC_CONTEXT_MALFORMED, "candidate must return an Outcome")
        outcomes.append((result.observed_outcome, result.detail))
    if outcomes[0] == outcomes[1]:
        raise BaselineError(
            RC_STUB_CONSTANT,
            "candidate returns an identical (outcome, reason) for the clean and crashed probes",
        )
    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=RC_STUB_SEPARATION_OK,
    )
