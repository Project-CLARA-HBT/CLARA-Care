"""COMPSAC-X04 in-network driver: runs the REAL B2 adapter against isolated PG16.

Executed INSIDE ``pg_research_net`` (the only namespace where the disposable research
cluster is addressable; it publishes no host port by design). Installs nothing silently:
the test harness launches this file inside the digest-pinned postgres:16.4 image with
python3 + python3-psycopg2 installed via apt. The driver:

1. pings the cluster and captures ``SHOW server_version`` verbatim;
2. builds the canonical clinical write-skew case (the B2 default schedule shape) and
   executes the REAL B2 adapter IN-PROCESS — importing the repo's
   ``evaluation.venue2027.compsac.baselines`` module mounted read-only at /work — with a
   genuine psycopg2 connection injected as ``ctx.pg_connection``. Two real threads hold
   concurrent SERIALIZABLE transactions so PostgreSQL's SSI machinery itself decides;
3. runs a READ COMMITTED contrast control (same interleaving) to prove the serialization
   abort is caused by SSI;
4. prints one JSON evidence line (marker-prefixed) consumed by the test module.

Failure semantics: every step records real output; no simulated outcome is ever produced.
Version: X04 driver 1.0.0.
"""

from __future__ import annotations

import json
import sys
import threading

sys.path.insert(0, "/work")

import psycopg2  # noqa: E402

from evaluation.venue2027.compsac import baselines as bl  # noqa: E402

DSN = "postgresql://research_app:research-only-throwaway@pg_research:5432/clara_research"
TABLE = "research_test.clinical_entities"
MARKER = "X04_EVIDENCE_JSON:"


def connect():
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    # The B2 adapter issues unqualified "clinical_entities" statements; pin every
    # session (including the adapter's) so they resolve inside research_test.
    cur = conn.cursor()
    cur.execute("SET search_path TO research_test, public")
    conn.commit()
    return conn


def reset_table(conn) -> None:
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS research_test")
    # The B2 adapter issues unqualified "clinical_entities" statements; pin the
    # session search_path so they resolve inside the research_test namespace.
    cur.execute("SET search_path TO research_test, public")
    cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
    cur.execute(
        f"CREATE TABLE {TABLE} ("
        " entity_id text PRIMARY KEY,"
        " version bigint NOT NULL DEFAULT 0,"
        " value text)"
    )
    # Canonical write-skew profile: two clinical entities at v1.
    cur.execute(
        f"INSERT INTO {TABLE} (entity_id, version, value) VALUES"
        " ('medication_order', 1, 'none'),"
        " ('allergy_list', 1, 'penicillin')"
    )
    conn.commit()


def run_pair(isolation: str) -> dict[str, object]:
    """Interleave two clinical writes racing on the OTHER's write target.

    T1 (medication_prescribe) re-reads medication_order and upserts allergy_list;
    T2 (allergy_update) re-reads allergy_list and upserts medication_order. Under
    READ COMMITTED both commit (write skew); under SERIALIZABLE, PostgreSQL's SSI
    machinery must abort at least one with SQLSTATE 40001 (or 40P01 under lock waits).
    """
    barrier = threading.Barrier(2)
    results: dict[str, dict[str, object]] = {}

    def worker(name: str, read_entity: str, write_entity: str, value: str) -> None:
        conn = connect()
        sqlstates: list[object] = []
        outcome = "COMMIT"
        reason = "OK"
        try:
            cur = conn.cursor()
            cur.execute(f"BEGIN ISOLATION LEVEL {isolation}")
            # Schema-check predicate re-read (SIREAD registration).
            cur.execute(f"SELECT version FROM {TABLE} WHERE entity_id = %s", (read_entity,))
            cur.fetchone()
            barrier.wait(timeout=30)
            # Conflict: write the entity the OTHER transaction read.
            cur.execute(
                f"INSERT INTO {TABLE} (entity_id, version, value) VALUES (%s, 1, %s)"
                f" ON CONFLICT (entity_id) DO UPDATE SET"
                f" version = {TABLE}.version + 1, value = EXCLUDED.value",
                (write_entity, value),
            )
            conn.commit()
        except Exception as exc:  # noqa: BLE001 - DB-API failures are arm outcomes
            sqlstates.append(getattr(exc, "pgcode", None))
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 - rollback failure must not mask the outcome
                pass
            outcome = "ABORT"
            reason = (
                "SERIALIZATION_FAILURE"
                if getattr(exc, "pgcode", None) in ("40001", "40P01")
                else (f"DB_ERROR:{getattr(exc, 'pgcode', None) or type(exc).__name__}")
            )
        finally:
            conn.close()
        results[name] = {"tx_id": name, "outcome": outcome, "reason_code": reason}
        if sqlstates:
            results[name]["sqlstate"] = sqlstates[0]

    t1 = threading.Thread(
        target=worker,
        args=("t1-medication-write", "medication_order", "allergy_list", "metformin-500mg"),
    )
    t2 = threading.Thread(
        target=worker, args=("t2-allergy-write", "allergy_list", "medication_order", "sulfa")
    )
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Post-run readback (fresh transaction): which writes actually installed?
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"SELECT entity_id, version, value FROM {TABLE} ORDER BY entity_id")
    rows = cur.fetchall()
    conn.commit()
    conn.close()

    txs = [results["t1-medication-write"], results["t2-allergy-write"]]
    committed = sum(1 for tx in txs if tx["outcome"] == "COMMIT")
    aborted = len(txs) - committed
    sqlstates = [tx.get("sqlstate") for tx in txs]
    versions = {str(r[0]): int(r[1]) for r in rows}
    # If both committed (write skew admitted), both installs happened.
    expected = {"allergy_list": 2, "medication_order": 2} if aborted == 0 else None
    if aborted == 1:
        # Server-side rollback: only the surviving tx's write is installed (v2),
        # the aborted tx's write target stays at v1.
        survivors_write = next(tx["tx_id"] for tx in txs if tx["outcome"] == "COMMIT")
        survivor_target = (
            "allergy_list" if survivors_write == "t1-medication-write" else "medication_order"
        )
        aborted_target = "medication_order" if survivor_target == "allergy_list" else "allergy_list"
        expected = {survivor_target: 2, aborted_target: 1}
    return {
        "isolation": isolation,
        "transactions": txs,
        "sqlstates": sqlstates,
        "committed": committed,
        "aborted": aborted,
        "aborted_write_installed": None
        if aborted == 0
        else versions == {"allergy_list": 2, "medication_order": 2},
        "final_versions": versions,
        "expected_final_versions": expected,
        "outcome": "ADMIT" if committed > 0 else "REJECT",
        "readback_rows": [[str(r[0]), int(r[1]), str(r[2])] for r in rows],
    }


def main() -> int:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SHOW server_version;")
    server_version = str(cur.fetchone()[0])
    cur.execute("SELECT 1")
    dsn_ok = cur.fetchone() == (1,)
    conn.commit()
    conn.close()

    # REAL B2 adapter outcome on the default schedule (write-skew pair), executed
    # in-process with a genuine PostgreSQL connection injected via ctx.pg_connection.
    # The adapter's genuine-PostgreSQL gate reads conn.server_version as a string like
    # "16.x ..."; psycopg2 exposes the numeric server_version_num (160004), so wrap the
    # live connection in a version-string facade (same live session, same backend).
    reset_table(connect())

    class _ServerVersionStrFacade:
        """Expose str(server_version) over the LIVE psycopg2 connection (pass-through)."""

        def __init__(self, live):
            self._live = live
            cur = live.cursor()
            cur.execute("SHOW server_version")
            self.server_version = str(cur.fetchone()[0])
            live.commit()

        def cursor(self):
            return self._live.cursor()

        def commit(self):
            return self._live.commit()

        def rollback(self):
            return self._live.rollback()

    exec_conn = connect()
    b2_outcome = bl.run_baseline(
        bl.B2_POSTGRES_SSI,
        {"case_id": "case-x04-pg-ssi"},
        {"pg_connection": _ServerVersionStrFacade(exec_conn)},
    )
    b2_detail = json.loads(b2_outcome.detail) if b2_outcome.counted_as_success else None
    exec_conn.close()

    reset_table(connect())
    ssi_pair = run_pair("SERIALIZABLE")

    reset_table(connect())
    rc_pair = run_pair("READ COMMITTED")

    evidence = {
        "task_id": "COMPSAC-X04_pg_ssi",
        "adapter": bl.B2_POSTGRES_SSI,
        "adapter_version": bl.COMPSAC_BASELINES_VERSION,
        "driver_version": "1.0.0",
        "driver_executed_in_network": "pg_research_net",
        "dsn_ok": dsn_ok,
        "server_version": server_version,
        "b2_default_schedule_outcome": {
            "observed_outcome": b2_outcome.observed_outcome,
            "counted_as_success": b2_outcome.counted_as_success,
            "detail": b2_outcome.detail,
            "parsed_detail": b2_detail,
        },
        "ssi_pair": ssi_pair,
        "read_committed_contrast": rc_pair,
        "retry_policy": {
            "max_attempts": 3,
            "idempotent_operation_id": "(case_id, tx_id)",
            "retries_executed_by_adapter": 0,
        },
    }
    print(MARKER + json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
