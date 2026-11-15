"""DSN-X04_outbox_reference — transactional-outbox reference implementation.

Purpose
-------
Faithful reference implementation of the strong practical baseline B1
("PostgreSQL atomic write + transactional outbox + idempotent consumer",
``research/venue2027/VENUES/dsn/RESEARCH_BLUEPRINT.md`` strong-baseline row B1)
for the DSN 2027 study "Recoverable Safety Journals for Crash-Consistent
AI-Mediated Health-State Mutations" (task contract
``research/venue2027/VENUES/dsn/TASKS/DSN-X04_outbox_reference.md``). The core
algorithm, executed verbatim by both backends:

1. One atomic transaction persists the clinical row, the outbox event and the
   consumer idempotency key (all three, or none).
2. The consumer is idempotent, keyed by the immutable operation ID: a redelivered
   event re-acks the original outcome without re-applying the side effect.
3. Delivery replays under at-least-once semantics until the event is
   acknowledged; every scheduled delivery that arrives is recorded (CASE_MATRIX
   DSN-CASE-04 counts all redeliveries), the effect is applied at most once.
4. The outcome reports the full retries (deliveries after the first, crash
   recoveries and redeliveries) and every durable write performed
   (the atomic row+outbox+idem transaction plus each effect write).

Backends (declared honestly, never conflated):

- ``in-memory-reference`` (default): a pure deterministic in-process store.
  No I/O, no hidden clock, no randomness; all timestamps are caller-supplied
  logical integers. This is the reference semantics used by the unit suite.
- ``postgresql-16.x``: when ``tx`` is a genuine PostgreSQL connection (any
  DB-API/psycopg-style object whose ``server_version`` identifies a
  PostgreSQL server), the same algorithm executes against that connection
  with real ``INSERT``/``UPDATE`` statements in a real transaction. The
  returned outcome's ``backend`` field names the observed server version, so
  a PostgreSQL condition is claimed only when PostgreSQL actually ran.

Allowed input
-------------
A JSON-serializable ``case`` mapping (exact schema, extra keys fail closed):
``case_id`` (str), ``operation_id`` (non-empty str), ``crash_point`` (one of
``none`` / ``pre_commit`` / ``post_commit_pre_response`` /
``pre_outbox_delivery`` / ``pre_consumer_ack``, mirroring CASE_MATRIX
DSN-CASE-02..04 windows), ``delivery_schedule`` (list of positive ints,
the at-least-once redelivery attempt indices), ``consent_epoch``
(non-negative int) and optional ``max_delivery_attempts`` (positive int).
``tx`` is either ``None`` (in-memory reference) or an injected connection
object. No production secret or patient data; no network; no live provider.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes carried on a first-class
:class:`Outcome` (never unhandled exceptions counted as outcomes):
``pre_commit`` crash yields ``REJECT`` / ``OP_NOT_DURABLE_CRASH_BEFORE_WRITE``
(retriable: recovery re-runs the same operation ID); a crashed-ack window
yields a committed outcome recovered by the idempotent replay; a tampered /
lost outbox row detected during replay yields ``INDETERMINATE`` /
``OUTBOX_ROW_LOST_DETECTED`` (never a silent success). Malformed cases are
wiring errors raised as :class:`OutboxReferenceError`; a non-PostgreSQL
connection passed as ``tx`` is refused with ``PG_CONNECTION_REQUIRED`` —
the reference is never simulated over SQLite or mocks claiming PG.

Version
-------
``OUTBOX_REFERENCE_VERSION = "clara.dsn.outbox-reference-v1"`` (additive-only
within v1; the outcome shape is version-pinned for the oracle).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Final

from evaluation.venue2027._shared.harness import (
    HARNESS_SYNTHETIC_OUTCOMES as NEVER_SUCCESS_OUTCOMES,
)
from evaluation.venue2027._shared.harness import OUTCOME_BUCKETS
from evaluation.venue2027._shared.harness import Outcome as HarnessOutcome

OUTBOX_REFERENCE_VERSION: Final[str] = "clara.dsn.outbox-reference-v1"

#: Backend labels (declared honestly in every outcome).
BACKEND_IN_MEMORY: Final[str] = "in-memory-reference"
BACKEND_POSTGRES_PREFIX: Final[str] = "postgresql-"

#: Stable reason codes (uppercase, machine-checkable).
RC_OP_COMMITTED: Final[str] = "OP_COMMITTED"
RC_OP_COMMITTED_IDEMPOTENT_RETRY: Final[str] = "OP_COMMITTED_IDEMPOTENT_RETRY"
RC_OP_NOT_DURABLE: Final[str] = "OP_NOT_DURABLE_CRASH_BEFORE_WRITE"
RC_CONSUMER_ACK_RECOVERED: Final[str] = "OP_COMMITTED_ACK_LOST_RECOVERED"
RC_OUTBOX_ROW_LOST: Final[str] = "OUTBOX_ROW_LOST_DETECTED"
RC_DELIVERY_BUDGET_EXHAUSTED: Final[str] = "DELIVERY_BUDGET_EXHAUSTED_INDETERMINATE"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_MISSING_FIELD: Final[str] = "CASE_MISSING_FIELD"
RC_CASE_BAD_TYPE: Final[str] = "CASE_BAD_TYPE"
RC_CASE_UNKNOWN_FIELD: Final[str] = "CASE_UNKNOWN_FIELD"
RC_CASE_EMPTY_OP_ID: Final[str] = "CASE_EMPTY_OPERATION_ID"
RC_CRASH_POINT_UNKNOWN: Final[str] = "CRASH_POINT_UNKNOWN"
RC_DELIVERY_SCHEDULE_BAD: Final[str] = "DELIVERY_SCHEDULE_MALFORMED"
RC_PG_CONNECTION_REQUIRED: Final[str] = "PG_CONNECTION_REQUIRED"

#: Crash cut points (mirrors baselines.CRASH_* / CASE_MATRIX DSN-CASE-02..04).
CRASH_NONE: Final[str] = "none"
CRASH_PRE_COMMIT: Final[str] = "pre_commit"
CRASH_POST_COMMIT_PRE_RESPONSE: Final[str] = "post_commit_pre_response"
CRASH_PRE_OUTBOX_DELIVERY: Final[str] = "pre_outbox_delivery"
CRASH_PRE_CONSUMER_ACK: Final[str] = "pre_consumer_ack"
CRASH_POINTS: Final[frozenset[str]] = frozenset(
    {
        CRASH_NONE,
        CRASH_PRE_COMMIT,
        CRASH_POST_COMMIT_PRE_RESPONSE,
        CRASH_PRE_OUTBOX_DELIVERY,
        CRASH_PRE_CONSUMER_ACK,
    }
)

#: Exact case schema (extra keys fail closed).
CASE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "case_id",
        "operation_id",
        "crash_point",
        "delivery_schedule",
        "consent_epoch",
        "max_delivery_attempts",
    }
)

_DEFAULT_MAX_DELIVERY_ATTEMPTS: Final[int] = 8


class OutboxReferenceError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class Case:
    """Validated, normalized case (JSON-serializable via to_dict)."""

    case_id: str
    operation_id: str
    crash_point: str
    delivery_schedule: tuple[int, ...]
    consent_epoch: int
    max_delivery_attempts: int = _DEFAULT_MAX_DELIVERY_ATTEMPTS

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "operation_id": self.operation_id,
            "crash_point": self.crash_point,
            "delivery_schedule": list(self.delivery_schedule),
            "consent_epoch": self.consent_epoch,
            "max_delivery_attempts": self.max_delivery_attempts,
        }


@dataclasses.dataclass
class Outcome:
    """Observed outcome of one outbox run (superset of the harness contract).

    ``observed_outcome`` / ``counted_as_success`` / ``retriable`` / ``detail``
    follow the shared harness :class:`Outcome` contract;
    ``backend``, ``full_retries``, ``durable_writes`` and ``deliveries``
    report the outbox-specific measurements required by the task contract.
    ``to_harness()`` projects onto the shared four-field type.
    """

    observed_outcome: str
    backend: str
    counted_as_success: bool = False
    retriable: bool = False
    detail: str = ""
    full_retries: int = 0
    durable_writes: int = 0
    deliveries: int = 0
    operation_id: str = ""
    crash_point: str = CRASH_NONE
    version: str = OUTBOX_REFERENCE_VERSION

    def __post_init__(self) -> None:
        if self.observed_outcome not in OUTCOME_BUCKETS:
            raise OutboxReferenceError(
                RC_CASE_BAD_TYPE,
                f"observed_outcome {self.observed_outcome!r} not in {sorted(OUTCOME_BUCKETS)}",
            )
        if self.observed_outcome in NEVER_SUCCESS_OUTCOMES and self.counted_as_success:
            raise OutboxReferenceError(
                RC_CASE_BAD_TYPE,
                f"observed_outcome {self.observed_outcome!r} can never be counted as success",
            )
        if isinstance(self.full_retries, bool) or not isinstance(self.full_retries, int):
            raise OutboxReferenceError(RC_CASE_BAD_TYPE, "full_retries must be an int")
        if isinstance(self.durable_writes, bool) or not isinstance(self.durable_writes, int):
            raise OutboxReferenceError(RC_CASE_BAD_TYPE, "durable_writes must be an int")

    def to_harness(self) -> HarnessOutcome:
        """Project onto the shared harness Outcome (four-field contract)."""
        return HarnessOutcome(
            observed_outcome=self.observed_outcome,
            counted_as_success=self.counted_as_success,
            retriable=self.retriable,
            detail=self.detail,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_outcome": self.observed_outcome,
            "backend": self.backend,
            "counted_as_success": self.counted_as_success,
            "retriable": self.retriable,
            "detail": self.detail,
            "full_retries": self.full_retries,
            "durable_writes": self.durable_writes,
            "deliveries": self.deliveries,
            "operation_id": self.operation_id,
            "crash_point": self.crash_point,
            "version": self.version,
        }


#: The shared harness outcome buckets and never-success set are imported at
#: module top (single source of truth for the false-zero ban).


def _validate_case(case: Mapping[str, Any]) -> Case:
    """Fail-closed case validation (stable reason codes, never guessed)."""
    if not isinstance(case, Mapping):
        raise OutboxReferenceError(RC_CASE_NOT_AN_OBJECT, f"case must be a mapping, got {type(case)}")
    unknown = sorted(set(map(str, case)) - CASE_KEYS)
    if unknown:
        raise OutboxReferenceError(RC_CASE_UNKNOWN_FIELD, f"unknown case keys: {unknown}")
    for field in ("case_id", "operation_id", "crash_point", "delivery_schedule", "consent_epoch"):
        if field not in case:
            raise OutboxReferenceError(RC_CASE_MISSING_FIELD, f"missing case field: {field}")
    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        raise OutboxReferenceError(RC_CASE_BAD_TYPE, "case_id must be a non-empty string")
    operation_id = case["operation_id"]
    if not isinstance(operation_id, str) or not operation_id:
        raise OutboxReferenceError(RC_CASE_EMPTY_OP_ID, "operation_id must be a non-empty string")
    crash_point = case["crash_point"]
    if not isinstance(crash_point, str) or crash_point not in CRASH_POINTS:
        raise OutboxReferenceError(
            RC_CRASH_POINT_UNKNOWN, f"crash_point {crash_point!r} not in {sorted(CRASH_POINTS)}"
        )
    schedule = case["delivery_schedule"]
    if not isinstance(schedule, list | tuple) or any(
        isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in schedule
    ):
        raise OutboxReferenceError(
            RC_DELIVERY_SCHEDULE_BAD,
            "delivery_schedule must be a list of positive ints (attempt indices)",
        )
    epoch = case["consent_epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise OutboxReferenceError(RC_CASE_BAD_TYPE, "consent_epoch must be a non-negative int")
    max_attempts = case.get("max_delivery_attempts", _DEFAULT_MAX_DELIVERY_ATTEMPTS)
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise OutboxReferenceError(
            RC_CASE_BAD_TYPE, "max_delivery_attempts must be a positive int"
        )
    return Case(
        case_id=case_id,
        operation_id=operation_id,
        crash_point=crash_point,
        delivery_schedule=tuple(schedule),
        consent_epoch=epoch,
        max_delivery_attempts=max_attempts,
    )


# ---------------------------------------------------------------------------
# Genuine-PostgreSQL gate (mirrors COMPSAC B2 discipline: never simulate PG).
# ---------------------------------------------------------------------------


def _pg_server_version(conn: Any) -> str | None:
    """Return the PostgreSQL server version string, or None if not genuine PG.

    Accepts DB-API-style connections exposing ``server_version`` (psycopg2 /
    DB-API convention), a psycopg3 ``conn.info.server_version`` numeric, or
    any object exposing ``get_server_version``; anything else (SQLite,
    mocks) is not a PostgreSQL connection and yields None.
    """
    version = getattr(conn, "server_version", None)
    if isinstance(version, str) and version.strip():
        return version.strip()
    if isinstance(version, int) and version > 0:
        return _pg_version_num_to_str(version)
    info = getattr(conn, "info", None)
    if info is not None:
        info_version = getattr(info, "server_version", None)
        if isinstance(info_version, int) and info_version > 0:
            return _pg_version_num_to_str(info_version)
    getter = getattr(conn, "get_server_version", None)
    if callable(getter):
        try:
            num = getter()
        except Exception:  # noqa: BLE001 - probe failure is not a PG identification
            return None
        if isinstance(num, int) and num > 0:
            return _pg_version_num_to_str(num)
    return None


def _pg_version_num_to_str(num: int) -> str:
    """Decode a libpq ``server_version`` number (e.g. 160004 -> '16.0.4')."""
    major = num // 10000
    minor = (num // 100) % 100
    patch = num % 100
    return f"{major}.{minor}.{patch}"


def _is_postgres_connection(conn: Any) -> bool:
    version = _pg_server_version(conn)
    if version is None:
        return False
    head = version.split(".")[0]
    return head.isdigit() and 9 <= int(head) <= 99


# ---------------------------------------------------------------------------
# In-memory reference (pure, deterministic).
# ---------------------------------------------------------------------------

_ROW_KEY: Final[str] = "outboxref:row:{}"
_OUTBOX_KEY: Final[str] = "outboxref:outbox:{}"
_IDEM_KEY: Final[str] = "outboxref:idem:{}"
_EFFECT_KEY: Final[str] = "outboxref:effect:{}"


class _MemoryTx:
    """In-memory transaction: all-or-nothing commit over a dict store.

    Buffered writes become durable only on ``commit()``; ``abort()`` drops
    them. This is the atomicity unit the outbox pattern relies on.
    """

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store
        self._buffer: dict[str, Any] = {}
        self.committed = False
        self.durable_writes = 0

    def put(self, key: str, value: Any) -> None:
        self._buffer[key] = value

    def get(self, key: str) -> Any:
        if key in self._buffer:
            return self._buffer[key]
        return self._store.get(key)

    def contains(self, key: str) -> bool:
        return key in self._buffer or key in self._store

    def commit(self) -> None:
        self._store.update(self._buffer)
        self.durable_writes += len(self._buffer)
        self.committed = True

    def abort(self) -> None:
        self._buffer.clear()


def _in_memory_run(
    case: Case, store: dict[str, Any], logical_time: int
) -> Outcome:
    """Execute the transactional-outbox algorithm over the in-memory store."""
    op = case.operation_id
    full_retries = 0
    deliveries = 0

    # --- Stage 1: the one atomic transaction (row + outbox + idem key). ---
    if case.crash_point == CRASH_PRE_COMMIT:
        # Crash before COMMIT: nothing durable anywhere; retry is safe.
        return Outcome(
            observed_outcome="REJECT",
            backend=BACKEND_IN_MEMORY,
            counted_as_success=False,
            retriable=True,
            detail=RC_OP_NOT_DURABLE,
            full_retries=0,
            durable_writes=0,
            deliveries=0,
            operation_id=op,
            crash_point=case.crash_point,
        )

    idem_present = _IDEM_KEY.format(op) in store
    if not idem_present:
        tx = _MemoryTx(store)
        tx.put(_ROW_KEY.format(op), {"operation_id": op, "consent_epoch": case.consent_epoch,
                                     "row_version": 1})
        tx.put(_OUTBOX_KEY.format(op), {"operation_id": op, "acked": False,
                                        "recorded_logical_time": logical_time})
        tx.put(_IDEM_KEY.format(op), {"operation_id": op, "effect_applied": False})
        if case.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
            tx.commit()  # durable, but the caller's ack/visibility is lost
            durable = tx.durable_writes
            # Recovery re-entry under the same operation id: idempotent dedup.
            full_retries += 1
            return Outcome(
                observed_outcome="ADMIT",
                backend=BACKEND_IN_MEMORY,
                counted_as_success=True,
                retriable=False,
                detail=RC_CONSUMER_ACK_RECOVERED,
                full_retries=full_retries,
                durable_writes=durable,
                deliveries=0,
                operation_id=op,
                crash_point=case.crash_point,
            )
        tx.commit()
        durable = tx.durable_writes
    else:
        durable = 0

    # --- Stage 2: at-least-once delivery, replay until acknowledged. ---
    outbox = store.get(_OUTBOX_KEY.format(op))
    if outbox is None:
        # Committed row without its outbox record (tamper / partial state):
        # ambiguous evidence, never coerced to a silent success.
        return Outcome(
            observed_outcome="INDETERMINATE",
            backend=BACKEND_IN_MEMORY,
            counted_as_success=False,
            retriable=False,
            detail=RC_OUTBOX_ROW_LOST,
            full_retries=full_retries,
            durable_writes=durable,
            deliveries=deliveries,
            operation_id=op,
            crash_point=case.crash_point,
        )

    idem = store[_IDEM_KEY.format(op)]
    effect_applied = bool(idem.get("effect_applied"))
    acked = bool(outbox.get("acked"))

    for index, attempt in enumerate(case.delivery_schedule):
        # Every scheduled delivery arrives at the consumer and is recorded
        # (CASE_MATRIX DSN-CASE-04: at-least-once redeliveries are all
        # counted, even ones the idempotent consumer dedups); the effect is
        # applied at most once via the idempotency key.
        deliveries += 1
        if index > 0 or attempt > 1:
            full_retries += 1
        if case.crash_point == CRASH_PRE_CONSUMER_ACK and index == 0:
            # The first delivery's consumer crashes before acking: the broker
            # redelivers; the idempotency key prevents a second effect.
            continue
        if not effect_applied:
            effect_applied = True
            idem["effect_applied"] = True
            store[_EFFECT_KEY.format(op)] = 1
            durable += 1
        acked = True
        outbox["acked"] = True

    if not acked:
        # Deterministic budget exhaustion: ambiguous, never a silent success.
        return Outcome(
            observed_outcome="INDETERMINATE",
            backend=BACKEND_IN_MEMORY,
            counted_as_success=False,
            retriable=True,
            detail=RC_DELIVERY_BUDGET_EXHAUSTED,
            full_retries=full_retries,
            durable_writes=durable,
            deliveries=deliveries,
            operation_id=op,
            crash_point=case.crash_point,
        )

    reason = RC_OP_COMMITTED if deliveries <= 1 and full_retries == 0 else (
        RC_OP_COMMITTED_IDEMPOTENT_RETRY
    )
    return Outcome(
        observed_outcome="ADMIT",
        backend=BACKEND_IN_MEMORY,
        counted_as_success=True,
        retriable=False,
        detail=reason,
        full_retries=full_retries,
        durable_writes=durable,
        deliveries=deliveries,
        operation_id=op,
        crash_point=case.crash_point,
    )


# ---------------------------------------------------------------------------
# Real-PostgreSQL path (executes only against a genuine PG server).
# ---------------------------------------------------------------------------

_PG_SCHEMA: Final[str] = "research_test"
_PG_TABLE_ROW: Final[str] = "outboxref_clinical_row"
_PG_TABLE_OUTBOX: Final[str] = "outboxref_outbox"
_PG_TABLE_IDEM: Final[str] = "outboxref_idempotency"
_PG_TABLE_EFFECT: Final[str] = "outboxref_effect"


def _pg_ensure_schema(conn: Any) -> None:
    """Create the reference tables (idempotent, research_test schema only)."""
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {_PG_SCHEMA}")
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {_PG_SCHEMA}.{_PG_TABLE_ROW} ("
            " operation_id text PRIMARY KEY, consent_epoch integer NOT NULL,"
            " row_version integer NOT NULL, payload text NOT NULL)"
        )
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {_PG_SCHEMA}.{_PG_TABLE_OUTBOX} ("
            " operation_id text PRIMARY KEY,"
            " acked boolean NOT NULL DEFAULT false,"
            " recorded_logical_time integer NOT NULL)"
        )
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {_PG_SCHEMA}.{_PG_TABLE_IDEM} ("
            " operation_id text PRIMARY KEY, effect_applied boolean NOT NULL DEFAULT false)"
        )
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {_PG_SCHEMA}.{_PG_TABLE_EFFECT} ("
            " operation_id text PRIMARY KEY, applied_at integer NOT NULL)"
        )


def _pg_run(case: Case, conn: Any, server_version: str, logical_time: int) -> Outcome:
    """Execute the transactional-outbox algorithm over genuine PostgreSQL.

    One transaction INSERTs the row, the outbox event and the idempotency
    key (all-or-none); the consumer dedups on the idempotency key and marks
    the outbox event acked inside its own transaction; replay continues
    until the event is acknowledged.
    """
    op = case.operation_id
    full_retries = 0
    deliveries = 0
    durable_writes = 0
    backend = f"{BACKEND_POSTGRES_PREFIX}{server_version}"

    _pg_ensure_schema(conn)

    if case.crash_point == CRASH_PRE_COMMIT:
        # The transaction is opened and deliberately rolled back: nothing
        # durable anywhere (atomicity window DSN-CASE-02).
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001 - rollback of an unopened tx is a no-op
            pass
        return Outcome(
            observed_outcome="REJECT",
            backend=backend,
            counted_as_success=False,
            retriable=True,
            detail=RC_OP_NOT_DURABLE,
            full_retries=0,
            durable_writes=0,
            deliveries=0,
            operation_id=op,
            crash_point=case.crash_point,
        )

    idem_present = False
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT 1 FROM {_PG_SCHEMA}.{_PG_TABLE_IDEM} WHERE operation_id = %s", (op,)
        )
        idem_present = cur.fetchone() is not None

    if not idem_present:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {_PG_SCHEMA}.{_PG_TABLE_ROW} (operation_id, consent_epoch,"
                    " row_version, payload) VALUES (%s, %s, 1, %s)",
                    (op, case.consent_epoch, f"synthetic:{case.case_id}"),
                )
                cur.execute(
                    f"INSERT INTO {_PG_SCHEMA}.{_PG_TABLE_OUTBOX} (operation_id, acked,"
                    " recorded_logical_time) VALUES (%s, false, %s)",
                    (op, logical_time),
                )
                cur.execute(
                    f"INSERT INTO {_PG_SCHEMA}.{_PG_TABLE_IDEM} (operation_id, effect_applied)"
                    " VALUES (%s, false)",
                    (op,),
                )
            conn.commit()
            durable_writes += 3
        except Exception:
            conn.rollback()
            raise
        if case.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
            # Committed but the caller's response/ack is lost: recovery
            # re-enters under the same operation id and dedups.
            full_retries += 1
            return Outcome(
                observed_outcome="ADMIT",
                backend=backend,
                counted_as_success=True,
                retriable=False,
                detail=RC_CONSUMER_ACK_RECOVERED,
                full_retries=full_retries,
                durable_writes=durable_writes,
                deliveries=0,
                operation_id=op,
                crash_point=case.crash_point,
            )

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT operation_id FROM {_PG_SCHEMA}.{_PG_TABLE_OUTBOX} WHERE operation_id = %s",
            (op,),
        )
        outbox_row = cur.fetchone()
    if outbox_row is None:
        # Committed idempotency key without its outbox record: lost outbox
        # row detected during replay; ambiguous evidence, fail closed.
        return Outcome(
            observed_outcome="INDETERMINATE",
            backend=backend,
            counted_as_success=False,
            retriable=False,
            detail=RC_OUTBOX_ROW_LOST,
            full_retries=full_retries,
            durable_writes=durable_writes,
            deliveries=deliveries,
            operation_id=op,
            crash_point=case.crash_point,
        )

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT effect_applied FROM {_PG_SCHEMA}.{_PG_TABLE_IDEM} WHERE operation_id = %s",
            (op,),
        )
        effect_applied = bool(cur.fetchone()[0])
        cur.execute(
            f"SELECT acked FROM {_PG_SCHEMA}.{_PG_TABLE_OUTBOX} WHERE operation_id = %s", (op,)
        )
        acked = bool(cur.fetchone()[0])

    for index, attempt in enumerate(case.delivery_schedule):
        # Every scheduled delivery arrives at the consumer and is recorded
        # (CASE_MATRIX DSN-CASE-04: at-least-once redeliveries are all
        # counted, even ones the idempotent consumer dedups); the effect is
        # applied at most once via the idempotency key.
        deliveries += 1
        if index > 0 or attempt > 1:
            full_retries += 1
        if case.crash_point == CRASH_PRE_CONSUMER_ACK and index == 0:
            # The first delivery's consumer crashes before acking: the broker
            # redelivers; the idempotency key prevents a second effect.
            continue
        try:
            with conn.cursor() as cur:
                if not effect_applied:
                    cur.execute(
                        f"INSERT INTO {_PG_SCHEMA}.{_PG_TABLE_EFFECT} (operation_id, applied_at)"
                        " VALUES (%s, %s)",
                        (op, logical_time),
                    )
                    cur.execute(
                        f"UPDATE {_PG_SCHEMA}.{_PG_TABLE_IDEM} SET effect_applied = true"
                        " WHERE operation_id = %s",
                        (op,),
                    )
                cur.execute(
                    f"UPDATE {_PG_SCHEMA}.{_PG_TABLE_OUTBOX} SET acked = true"
                    " WHERE operation_id = %s",
                    (op,),
                )
            conn.commit()
            durable_writes += 1 if effect_applied else 0
            effect_applied = True
            acked = True
        except Exception:
            conn.rollback()
            raise

    if not acked:
        return Outcome(
            observed_outcome="INDETERMINATE",
            backend=backend,
            counted_as_success=False,
            retriable=True,
            detail=RC_DELIVERY_BUDGET_EXHAUSTED,
            full_retries=full_retries,
            durable_writes=durable_writes,
            deliveries=deliveries,
            operation_id=op,
            crash_point=case.crash_point,
        )

    reason = RC_OP_COMMITTED if deliveries <= 1 and full_retries == 0 else (
        RC_OP_COMMITTED_IDEMPOTENT_RETRY
    )
    return Outcome(
        observed_outcome="ADMIT",
        backend=backend,
        counted_as_success=True,
        retriable=False,
        detail=reason,
        full_retries=full_retries,
        durable_writes=durable_writes,
        deliveries=deliveries,
        operation_id=op,
        crash_point=case.crash_point,
    )


# ---------------------------------------------------------------------------
# Public entry point (manifest signature: run_outbox(case, tx) -> Outcome).
# ---------------------------------------------------------------------------


def run_outbox(
    case: Mapping[str, Any],
    tx: Any = None,
    *,
    store: dict[str, Any] | None = None,
    logical_time: int = 0,
) -> Outcome:
    """Run the transactional-outbox reference for one case.

    ``tx=None`` (or omitted) runs the pure in-memory reference and labels the
    outcome ``in-memory-reference``. When ``tx`` is provided it must be a
    genuine PostgreSQL connection; the same algorithm then executes with real
    SQL in real transactions and the outcome labels the observed server
    version (``postgresql-16.4 ...``). A non-PostgreSQL connection is refused
    with ``PG_CONNECTION_REQUIRED`` — never simulated over SQLite or mocks.
    """
    validated = _validate_case(case)
    if tx is None:
        return _in_memory_run(validated, store if store is not None else {}, logical_time)
    server_version = _pg_server_version(tx)
    if not _is_postgres_connection(tx):
        raise OutboxReferenceError(
            RC_PG_CONNECTION_REQUIRED,
            f"tx does not identify a genuine PostgreSQL server (version {server_version!r});"
            " the outbox reference is never simulated over a non-PostgreSQL connection",
        )
    return _pg_run(validated, tx, str(server_version), logical_time)


# ---------------------------------------------------------------------------
# Deterministic self-check (module execution, mirrors sibling modules).
# ---------------------------------------------------------------------------


def _demo() -> dict[str, Any]:
    clean = run_outbox(
        {
            "case_id": "demo-clean",
            "operation_id": "op:demo-clean",
            "crash_point": CRASH_NONE,
            "delivery_schedule": [1],
            "consent_epoch": 3,
        }
    )
    replay = run_outbox(
        {
            "case_id": "demo-replay",
            "operation_id": "op:demo-replay",
            "crash_point": CRASH_NONE,
            "delivery_schedule": [1, 2, 3],
            "consent_epoch": 3,
        },
        store={},
    )
    crashed = run_outbox(
        {
            "case_id": "demo-crash",
            "operation_id": "op:demo-crash",
            "crash_point": CRASH_PRE_COMMIT,
            "delivery_schedule": [1],
            "consent_epoch": 3,
        }
    )
    return {
        "version": OUTBOX_REFERENCE_VERSION,
        "results": {
            "clean_commit": clean.to_dict(),
            "triple_replay_dedup": replay.to_dict(),
            "pre_commit_crash": crashed.to_dict(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="DSN-X04 transactional-outbox reference self-check")
    parser.add_argument("--json", action="store_true", help="print the self-check as JSON")
    args = parser.parse_args(argv)
    report = _demo()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for name, result in report["results"].items():
            print(
                f"{name}: {result['observed_outcome']} ({result['detail']})"
                f" backend={result['backend']}"
                f" full_retries={result['full_retries']}"
                f" durable_writes={result['durable_writes']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
