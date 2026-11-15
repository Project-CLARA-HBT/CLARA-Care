"""CLARA-Care 2027 DSN task DSN-X04_outbox_reference — reference test suite.

Purpose
-------
Positive and adversarial vectors for the transactional-outbox reference
implementation ``evaluation/venue2027/dsn/outbox_reference.py`` (the strong
practical baseline B1 of the DSN 2027 study "Recoverable Safety Journals for
Crash-Consistent AI-Mediated Health-State Mutations"), driven through its
public dispatch entry ``run_outbox(case, tx) -> Outcome`` — never
reimplemented, never stubbed.

Positive vectors (guarantee holds):
- One atomic transaction persists the clinical row AND the outbox event AND
  the idempotency key: a clean case commits with exactly one effect record
  and the full triple present in the store.
- The consumer is idempotent keyed by the operation ID: a duplicate delivery
  re-acks the original outcome with zero additional durable writes and zero
  additional effects.
- Triple broker replay (DSN-CASE-04): three scheduled deliveries produce one
  effect and two counted retries.
- Replay until acknowledged: after a consumer crash before ack
  (``pre_consumer_ack``), the redelivery completes the operation exactly
  once; after a lost response (``post_commit_pre_response``), recovery
  re-entry under the same operation ID dedups without re-applying.
- The outcome reports full retries and durable writes on every run.

Adversarial vectors (fail closed):
- ``pre_commit`` crash: nothing durable anywhere, ``REJECT`` retriable,
  never counted as success; a subsequent retry of the same operation ID
  succeeds exactly once (no double effect).
- Consumer crash before ack with no redelivery budget: ``INDETERMINATE``
  (``DELIVERY_BUDGET_EXHAUSTED_INDETERMINATE``), never a phantom success.
- Lost outbox row (tamper / partial state) detected during replay:
  ``INDETERMINATE`` / ``OUTBOX_ROW_LOST_DETECTED``, never a silent success.
- A SQLite connection passed as ``tx`` is refused with
  ``PG_CONNECTION_REQUIRED``: the reference is never simulated over a
  non-PostgreSQL connection and never claims a PG condition from one.
- Malformed cases (non-mapping, unknown keys, missing/badly-typed fields,
  unknown crash point, bad delivery schedule) raise OutboxReferenceError
  with stable reason codes (wiring errors, not counted outcomes).
- Determinism: identical (case, fresh store) pairs yield identical outcomes.

Real-PostgreSQL path
--------------------
Gated at runtime on genuine availability of the isolated research cluster
(``infra/research/venue2027/docker-compose.pg.yaml``; PG 16.4, host
``pg_research`` reachable only from inside ``pg_research_net`` per the
no-host-port isolation contract, probed from within the compose network).
When the cluster is reachable, the same positive and adversarial vectors
execute against real PostgreSQL and the outcome's ``backend`` field is
asserted to name the real server version. When it is not reachable, those
tests SKIP with the real connection error as the skip reason — the
in-memory vectors never claim a PostgreSQL condition.

All fixtures are synthetic (no PHI/PII, no network, no live provider, no
hidden clock or randomness). Version: pinned via ``OUTBOX_REFERENCE_VERSION``.
"""

from __future__ import annotations

import socket

import pytest

from evaluation.venue2027._shared.harness import Outcome as HarnessOutcome
from evaluation.venue2027.dsn.outbox_reference import (
    BACKEND_IN_MEMORY,
    CASE_KEYS,
    CRASH_NONE,
    CRASH_POINTS,
    CRASH_POST_COMMIT_PRE_RESPONSE,
    CRASH_PRE_COMMIT,
    CRASH_PRE_CONSUMER_ACK,
    CRASH_PRE_OUTBOX_DELIVERY,
    OUTBOX_REFERENCE_VERSION,
    RC_CASE_BAD_TYPE,
    RC_CASE_EMPTY_OP_ID,
    RC_CASE_MISSING_FIELD,
    RC_CASE_NOT_AN_OBJECT,
    RC_CASE_UNKNOWN_FIELD,
    RC_CONSUMER_ACK_RECOVERED,
    RC_CRASH_POINT_UNKNOWN,
    RC_DELIVERY_BUDGET_EXHAUSTED,
    RC_DELIVERY_SCHEDULE_BAD,
    RC_OP_COMMITTED,
    RC_OP_COMMITTED_IDEMPOTENT_RETRY,
    RC_OP_NOT_DURABLE,
    RC_OUTBOX_ROW_LOST,
    RC_PG_CONNECTION_REQUIRED,
    Case,
    OutboxReferenceError,
    Outcome,
    run_outbox,
)

OUTBOX_REF_TESTS_VERSION = "1.0.0"

_EFFECT_PREFIX = "outboxref:effect:"


def make_case(
    case_id: str = "case-0001",
    operation_id: str = "op:0001",
    crash_point: str = CRASH_NONE,
    delivery_schedule: tuple[int, ...] | list[int] = (1,),
    consent_epoch: int = 3,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "operation_id": operation_id,
        "crash_point": crash_point,
        "delivery_schedule": list(delivery_schedule),
        "consent_epoch": consent_epoch,
    }


def fresh_store() -> dict[str, object]:
    return {}


def effect_count(store: dict[str, object]) -> int:
    return len([k for k in store if str(k).startswith(_EFFECT_PREFIX)])


# ---------------------------------------------------------------------------
# Positive controls: row + outbox atomic; idempotent consumer; replay to ack.
# ---------------------------------------------------------------------------


class TestPositiveAtomicCommit:
    def test_clean_run_commits_row_and_outbox_atomically(self) -> None:
        """One transaction persists row AND outbox: the full triple is durable."""
        store = fresh_store()
        outcome = run_outbox(make_case(), store=store)
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True
        assert outcome.backend == BACKEND_IN_MEMORY
        assert outcome.detail == RC_OP_COMMITTED
        # The atomic transaction wrote row + outbox + idem key together, plus
        # the one effect write in the delivery stage.
        assert outcome.durable_writes == 4
        assert store["outboxref:row:op:0001"] is not None
        assert store["outboxref:outbox:op:0001"]["acked"] is True
        assert store["outboxref:idem:op:0001"]["effect_applied"] is True
        assert effect_count(store) == 1

    def test_row_and_outbox_refer_to_same_operation_id(self) -> None:
        """CASE_MATRIX DSN-CASE-01: lineage, row and outbox name one operation."""
        store = fresh_store()
        outcome = run_outbox(make_case(operation_id="op:lineage"), store=store)
        row = store["outboxref:row:op:lineage"]
        outbox = store["outboxref:outbox:op:lineage"]
        idem = store["outboxref:idem:op:lineage"]
        assert row["operation_id"] == "op:lineage"
        assert outbox["operation_id"] == "op:lineage"
        assert idem["operation_id"] == "op:lineage"
        assert outcome.operation_id == "op:lineage"


class TestPositiveIdempotentConsumer:
    def test_duplicate_delivery_is_idempotent(self) -> None:
        """A redelivered event re-acks without re-applying the effect."""
        store = fresh_store()
        first = run_outbox(make_case(), store=store)
        second = run_outbox(make_case(), store=store)
        assert first.observed_outcome == "ADMIT"
        assert second.observed_outcome == "ADMIT"
        # Zero additional durable writes and zero additional effects.
        assert second.durable_writes == 0
        assert effect_count(store) == 1
        assert store["outboxref:outbox:op:0001"]["acked"] is True

    def test_triple_broker_replay_applies_effect_once(self) -> None:
        """CASE_MATRIX DSN-CASE-04: three deliveries recorded, one effect."""
        store = fresh_store()
        outcome = run_outbox(make_case(delivery_schedule=[1, 2, 3]), store=store)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_OP_COMMITTED_IDEMPOTENT_RETRY
        assert outcome.deliveries == 3  # all redeliveries recorded
        assert outcome.full_retries == 2  # two deliveries after the first
        assert effect_count(store) == 1

    def test_replay_until_acknowledged_after_consumer_crash(self) -> None:
        """pre_consumer_ack crash + redelivery: completes exactly once."""
        store = fresh_store()
        outcome = run_outbox(
            make_case(crash_point=CRASH_PRE_CONSUMER_ACK, delivery_schedule=[1, 2]),
            store=store,
        )
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.deliveries == 2
        assert outcome.full_retries == 1
        assert effect_count(store) == 1
        assert store["outboxref:outbox:op:0001"]["acked"] is True

    def test_recovery_after_lost_response_dedups(self) -> None:
        """CASE_MATRIX DSN-CASE-03: committed row survives, recovery re-acks."""
        store = fresh_store()
        crashed = run_outbox(
            make_case(crash_point=CRASH_POST_COMMIT_PRE_RESPONSE), store=store
        )
        assert crashed.observed_outcome == "ADMIT"
        assert crashed.detail == RC_CONSUMER_ACK_RECOVERED
        assert crashed.full_retries == 1
        assert crashed.durable_writes == 3  # the one atomic transaction
        # Recovery re-entry under the same operation id: the delivery replays
        # (one delivery recorded), applies the effect exactly once, and never
        # re-runs the atomic transaction.
        recovered = run_outbox(make_case(), store=store)
        assert recovered.observed_outcome == "ADMIT"
        assert recovered.deliveries == 1
        assert effect_count(store) == 1

    def test_reports_full_retries_and_durable_writes(self) -> None:
        """Every outcome carries the retry and durable-write measurements."""
        store = fresh_store()
        clean = run_outbox(make_case(), store=store)
        assert clean.full_retries == 0 and clean.durable_writes == 4
        store2 = fresh_store()
        replayed = run_outbox(
            make_case(crash_point=CRASH_PRE_CONSUMER_ACK, delivery_schedule=[1, 2, 3]),
            store=store2,
        )
        assert replayed.full_retries == 2 and replayed.deliveries == 3

    def test_outcome_projects_onto_harness_contract(self) -> None:
        """to_harness() yields the shared four-field harness Outcome."""
        store = fresh_store()
        outcome = run_outbox(make_case(), store=store)
        harness = outcome.to_harness()
        assert not isinstance(harness, Outcome)  # harness type, not the module type
        assert isinstance(harness, HarnessOutcome)
        assert harness.observed_outcome == "ADMIT"
        assert harness.counted_as_success is True
        assert harness.retriable is False


# ---------------------------------------------------------------------------
# Adversarial controls.
# ---------------------------------------------------------------------------


class TestAdversarialCrashWindows:
    def test_pre_commit_crash_is_never_a_success(self) -> None:
        """CASE_MATRIX DSN-CASE-02: nothing durable, REJECT retriable."""
        store = fresh_store()
        outcome = run_outbox(make_case(crash_point=CRASH_PRE_COMMIT), store=store)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is False
        assert outcome.retriable is True
        assert outcome.detail == RC_OP_NOT_DURABLE
        assert outcome.durable_writes == 0
        assert not store  # nothing leaked into the durable store

    def test_retry_after_pre_commit_crash_succeeds_exactly_once(self) -> None:
        """Recovery re-runs the same operation id: one commit, one effect."""
        store = fresh_store()
        crashed = run_outbox(make_case(crash_point=CRASH_PRE_COMMIT), store=store)
        retried = run_outbox(make_case(crash_point=CRASH_NONE), store=store)
        assert crashed.observed_outcome == "REJECT"
        assert retried.observed_outcome == "ADMIT"
        assert effect_count(store) == 1

    def test_consumer_crash_before_ack_without_redelivery_is_indeterminate(self) -> None:
        """A budget-exhausted replay never becomes a phantom success."""
        store = fresh_store()
        outcome = run_outbox(
            make_case(crash_point=CRASH_PRE_CONSUMER_ACK, delivery_schedule=[1]),
            store=store,
        )
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_DELIVERY_BUDGET_EXHAUSTED
        assert outcome.counted_as_success is False
        assert outcome.retriable is True

    def test_redelivery_after_consumer_crash_has_no_duplicate_effect(self) -> None:
        """The idempotency key caps the effect at one across the crash window."""
        store = fresh_store()
        crashed = run_outbox(
            make_case(crash_point=CRASH_PRE_CONSUMER_ACK, delivery_schedule=[1]),
            store=store,
        )
        assert crashed.observed_outcome == "INDETERMINATE"
        recovered = run_outbox(make_case(delivery_schedule=[2]), store=store)
        assert recovered.observed_outcome == "ADMIT"
        assert recovered.detail == RC_OP_COMMITTED_IDEMPOTENT_RETRY
        assert recovered.full_retries == 1
        assert effect_count(store) == 1  # exactly once across both runs

    def test_pre_outbox_delivery_window_replays_to_ack(self) -> None:
        """CASE_MATRIX DSN-CASE-07 shape: committed, delivery pending, then ack."""
        store = fresh_store()
        outcome = run_outbox(
            make_case(crash_point=CRASH_PRE_OUTBOX_DELIVERY, delivery_schedule=[1, 2]),
            store=store,
        )
        assert outcome.observed_outcome == "ADMIT"
        assert effect_count(store) == 1
        assert store["outboxref:outbox:op:0001"]["acked"] is True


class TestAdversarialEvidenceIntegrity:
    def test_lost_outbox_row_is_detected_not_silent(self) -> None:
        """Committed idem key without its outbox row: INDETERMINATE, fail closed."""
        store = fresh_store()
        run_outbox(make_case(operation_id="op:tamper"), store=store)
        del store["outboxref:outbox:op:tamper"]  # tamper: outbox row lost
        outcome = run_outbox(make_case(operation_id="op:tamper"), store=store)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_OUTBOX_ROW_LOST
        assert outcome.counted_as_success is False
        assert outcome.retriable is False

    def test_pre_commit_plus_lost_outbox_row_stays_fail_closed(self) -> None:
        """A tampered store after a crash never yields a positive outcome."""
        store = fresh_store()
        run_outbox(make_case(operation_id="op:torn"), store=store)
        del store["outboxref:outbox:op:torn"]
        outcome = run_outbox(
            make_case(operation_id="op:torn", crash_point=CRASH_PRE_OUTBOX_DELIVERY),
            store=store,
        )
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.counted_as_success is False


class TestAdversarialBackendHonesty:
    def test_sqlite_connection_is_refused_not_simulated(self) -> None:
        """A SQLite connection never satisfies the real-PG path (no fake PG)."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        with pytest.raises(OutboxReferenceError) as exc:
            run_outbox(make_case(), conn)
        assert exc.value.reason_code == RC_PG_CONNECTION_REQUIRED

    def test_mock_connection_without_server_version_is_refused(self) -> None:
        """A mock lacking a genuine PostgreSQL server identity is refused."""

        class _FakeConn:
            server_version = "not-a-pg-server"

        with pytest.raises(OutboxReferenceError) as exc:
            run_outbox(make_case(), _FakeConn())
        assert exc.value.reason_code == RC_PG_CONNECTION_REQUIRED


class TestAdversarialMalformedInput:
    @pytest.mark.parametrize(
        ("case", "reason"),
        [
            ("not-a-mapping", RC_CASE_NOT_AN_OBJECT),
            ({"operation_id": "op:1"}, RC_CASE_MISSING_FIELD),
            (
                {
                    "case_id": "c",
                    "operation_id": "op:1",
                    "crash_point": "none",
                    "delivery_schedule": [1],
                    "consent_epoch": 3,
                    "extra": 1,
                },
                RC_CASE_UNKNOWN_FIELD,
            ),
            (
                make_case(operation_id=""),
                RC_CASE_EMPTY_OP_ID,
            ),
            (
                make_case(crash_point="mid_flight"),
                RC_CRASH_POINT_UNKNOWN,
            ),
            (
                make_case(delivery_schedule=[0, -1]),
                RC_DELIVERY_SCHEDULE_BAD,
            ),
            (
                make_case(delivery_schedule=["1"]),
                RC_DELIVERY_SCHEDULE_BAD,
            ),
            (
                make_case(consent_epoch=-1),
                RC_CASE_BAD_TYPE,
            ),
            (
                {**make_case(), "max_delivery_attempts": 0},
                RC_CASE_BAD_TYPE,
            ),
        ],
    )
    def test_malformed_case_raises_stable_reason_code(
        self, case: object, reason: str
    ) -> None:
        with pytest.raises(OutboxReferenceError) as exc:
            run_outbox(case)  # type: ignore[arg-type]
        assert exc.value.reason_code == reason


class TestDeterminism:
    def test_identical_case_fresh_store_gives_identical_outcome(self) -> None:
        a = run_outbox(make_case(), store=fresh_store())
        b = run_outbox(make_case(), store=fresh_store())
        assert a.to_dict() == b.to_dict()

    def test_case_schema_is_exact(self) -> None:
        assert CASE_KEYS == frozenset(
            {
                "case_id",
                "operation_id",
                "crash_point",
                "delivery_schedule",
                "consent_epoch",
                "max_delivery_attempts",
            }
        )
        assert CRASH_POINTS == frozenset(
            {
                CRASH_NONE,
                CRASH_PRE_COMMIT,
                CRASH_POST_COMMIT_PRE_RESPONSE,
                CRASH_PRE_OUTBOX_DELIVERY,
                CRASH_PRE_CONSUMER_ACK,
            }
        )
        assert OUTBOX_REFERENCE_VERSION.startswith("clara.dsn.outbox-reference-")
        case = Case(
            case_id="c",
            operation_id="op:1",
            crash_point=CRASH_NONE,
            delivery_schedule=(1,),
            consent_epoch=3,
        )
        assert case.to_dict()["delivery_schedule"] == [1]  # JSON-serializable


# ---------------------------------------------------------------------------
# Real-PostgreSQL path: genuine integration against the isolated research
# cluster (docker-compose.pg.yaml). Probed from inside the compose network —
# the cluster publishes no host port by design, so host-level probes cannot
# (and must not) reach it. Skips honestly when the cluster is unavailable;
# a skip never claims a PostgreSQL condition.
# ---------------------------------------------------------------------------

_PG_DSN = "postgresql://research_app:research-only-throwaway@pg_research:5432/clara_research"
_PG_PROBE_TIMEOUT = 3.0


def _pg_reachable_from_inside_network() -> bool:
    """True only when the isolated cluster resolves inside pg_research_net.

    The compose cluster is named-host-only (``pg_research``); on the host this
    probe fails to resolve and the PG tests skip — by isolation contract.
    """
    try:
        socket.getaddrinfo("pg_research", 5432, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    try:
        with socket.create_connection(("pg_research", 5432), timeout=_PG_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


_PG_AVAILABLE = _pg_reachable_from_inside_network()
_PG_SKIP_REASON = (
    "isolated research PostgreSQL cluster not reachable from this execution"
    " context (compose network pg_research_net only; no host port by design)"
)

pytestmark_pg = pytest.mark.skipif(not _PG_AVAILABLE, reason=_PG_SKIP_REASON)


def _pg_conn() -> object:
    import psycopg

    return psycopg.connect(_PG_DSN, connect_timeout=5)


@pytest.mark.skipif(not _PG_AVAILABLE, reason=_PG_SKIP_REASON)
class TestRealPostgresPath:
    """Vectors that only run against the genuine isolated PG 16 cluster."""

    def _clean_operation(self, op: str) -> None:
        """Reset one operation's rows; tables are created by run_outbox lazily."""
        conn = _pg_conn()
        try:
            from evaluation.venue2027.dsn.outbox_reference import _pg_ensure_schema

            _pg_ensure_schema(conn)
            conn.commit()
            with conn.cursor() as cur:
                for table in (
                    "outboxref_effect",
                    "outboxref_idempotency",
                    "outboxref_outbox",
                    "outboxref_clinical_row",
                ):
                    cur.execute(
                        f"DELETE FROM research_test.{table} WHERE operation_id = %s", (op,)
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def test_clean_commit_on_real_postgres(self) -> None:
        """Row + outbox + idem key commit in one real PG transaction."""
        conn = _pg_conn()
        try:
            self._clean_operation("op:pg-clean")
            outcome = run_outbox(make_case(operation_id="op:pg-clean"), conn)
            assert isinstance(outcome, Outcome)
            assert outcome.observed_outcome == "ADMIT"
            assert outcome.backend.startswith("postgresql-16.")
            assert outcome.detail == RC_OP_COMMITTED
            assert outcome.durable_writes == 3
            # Durable evidence is really in the database, not in-process state.
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT acked FROM research_test.outboxref_outbox"
                    " WHERE operation_id = %s",
                    ("op:pg-clean",),
                )
                assert cur.fetchone()[0] is True
                cur.execute(
                    "SELECT count(*) FROM research_test.outboxref_effect"
                    " WHERE operation_id = %s",
                    ("op:pg-clean",),
                )
                assert cur.fetchone()[0] == 1
        finally:
            conn.close()

    def test_pre_commit_crash_writes_nothing_on_real_postgres(self) -> None:
        """The rollback path leaves zero durable rows behind."""
        conn = _pg_conn()
        try:
            self._clean_operation("op:pg-crash")
            outcome = run_outbox(
                make_case(operation_id="op:pg-crash", crash_point=CRASH_PRE_COMMIT), conn
            )
            assert outcome.observed_outcome == "REJECT"
            assert outcome.durable_writes == 0
            with conn.cursor() as cur:
                for table in (
                    "outboxref_clinical_row",
                    "outboxref_outbox",
                    "outboxref_idempotency",
                ):
                    cur.execute(
                        f"SELECT count(*) FROM research_test.{table}"
                        " WHERE operation_id = %s",
                        ("op:pg-crash",),
                    )
                    assert cur.fetchone()[0] == 0
        finally:
            conn.close()

    def test_idempotent_redelivery_on_real_postgres(self) -> None:
        """Duplicate delivery over PG re-acks with exactly one effect row."""
        conn = _pg_conn()
        try:
            self._clean_operation("op:pg-dup")
            first = run_outbox(make_case(operation_id="op:pg-dup"), conn)
            second = run_outbox(make_case(operation_id="op:pg-dup"), conn)
            assert first.observed_outcome == "ADMIT"
            assert second.observed_outcome == "ADMIT"
            # The redelivery re-acks (one durable ack UPDATE) but never
            # re-runs the atomic transaction nor re-applies the effect.
            assert second.durable_writes <= 1
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM research_test.outboxref_effect"
                    " WHERE operation_id = %s",
                    ("op:pg-dup",),
                )
                assert cur.fetchone()[0] == 1
        finally:
            conn.close()

    def test_post_commit_recovery_on_real_postgres(self) -> None:
        """Lost-response recovery re-enters and dedups over real PG."""
        conn = _pg_conn()
        try:
            self._clean_operation("op:pg-ack")
            crashed = run_outbox(
                make_case(operation_id="op:pg-ack", crash_point=CRASH_POST_COMMIT_PRE_RESPONSE),
                conn,
            )
            assert crashed.detail == RC_CONSUMER_ACK_RECOVERED
            assert crashed.durable_writes == 3
            recovered = run_outbox(make_case(operation_id="op:pg-ack"), conn)
            assert recovered.observed_outcome == "ADMIT"
            assert recovered.durable_writes == 0
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM research_test.outboxref_effect"
                    " WHERE operation_id = %s",
                    ("op:pg-ack",),
                )
                assert cur.fetchone()[0] == 1
        finally:
            conn.close()
