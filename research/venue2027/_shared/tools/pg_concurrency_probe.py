"""SH-postgres_isolation concurrency driver.

Runs INSIDE the isolated compose network (the research cluster publishes no
host port by design). Executed via:

    docker run --rm --network pg_research_net -v <repo>:/work -w /work \
        python:3.12-slim python3 research/venue2027/_shared/tools/pg_concurrency_probe.py \
        <dsn-url> <out-json>

Behavior (fail-closed, evidence-producing):
  1. Refuse the DSN unless pg_guard accepts it (isolated research shape only).
  2. Assert the backend is PostgreSQL 16 via `SHOW server_version`.
  3. Run two concurrent psycopg transactions (independent connections) writing
     distinct rows; a reader transaction started BEFORE the second writer's
     commit must NOT see it, and a reader after BOTH commits must see both
     rows (independent commit visibility under READ COMMITTED).
  4. Emit a JSON evidence record to <out-json> with the observed
     server_version, the visibility results, and input SHAs.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading

sys.path.insert(0, "/work/research/venue2027/_shared/tools")

import pg_guard  # noqa: E402
import psycopg  # noqa: E402


def _sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: pg_concurrency_probe.py <dsn> <out-json>", file=sys.stderr)
        return 2
    dsn, out_path = sys.argv[1], sys.argv[2]

    # Fail-closed: only the isolated research DSN shape is accepted.
    pg_guard.assert_isolated_database_url(dsn)

    evidence: dict[str, object] = {
        "tool": "pg_concurrency_probe",
        "dsn_host": "pg_research",
        "guard_version": pg_guard.PG_GUARD_VERSION,
    }

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version")
            server_version = str(cur.fetchone()[0])
            evidence["server_version"] = server_version
            evidence["server_version_num"] = None
            cur.execute("SHOW server_version_num")
            evidence["server_version_num"] = str(cur.fetchone()[0])
            evidence["isolation_level"] = conn.info.transaction_status.name

        if not server_version.startswith("16"):
            evidence["verdict"] = "FAIL_VERSION"
            json.dump(evidence, open(out_path, "w"), indent=2)
            print(json.dumps(evidence))
            return 1

        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS research_test")
            cur.execute("DROP TABLE IF EXISTS research_test.commit_visibility")
            cur.execute(
                "CREATE TABLE research_test.commit_visibility ("
                " id integer PRIMARY KEY, writer text NOT NULL,"
                " created_at timestamptz NOT NULL DEFAULT now())"
            )
        conn.commit()

        results: dict[str, object] = {}
        errors: list[str] = []
        inserted = {"A": threading.Event(), "B": threading.Event()}
        release = {"A": threading.Event(), "B": threading.Event()}

        def writer(tag: str, row_id: int) -> None:
            try:
                with psycopg.connect(dsn) as wconn:
                    with wconn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO research_test.commit_visibility (id, writer)"
                            " VALUES (%s, %s)",
                            (row_id, tag),
                        )
                    # Row is INSERTed but NOT committed; main decides when.
                    inserted[tag].set()
                    if not release[tag].wait(timeout=60):
                        raise TimeoutError(f"writer-{tag}: release timeout")
                    wconn.commit()
            except Exception as exc:  # noqa: BLE001 - evidence, not control flow
                errors.append(f"writer-{tag}: {type(exc).__name__}: {exc}")
                inserted[tag].set()
                release[tag].set()

        def read_count() -> tuple[int, str]:
            with psycopg.connect(dsn) as rconn:
                with rconn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*) FROM research_test.commit_visibility"
                    )
                    cnt = cur.fetchone()[0]
                    cur.execute("SELECT pg_current_snapshot()::text")
                    return int(cnt), str(cur.fetchone()[0])

        # Deterministic independent-commit-visibility schedule:
        #   1. Both writers INSERT (uncommitted) and hold.
        #   2. Reader1: neither uncommitted row is visible (count == 0).
        #   3. Writer A commits; Reader2 sees exactly A's row (count == 1),
        #      B's still-uncommitted row remains invisible.
        #   4. Writer B commits; Reader3 sees both rows: B's commit became
        #      visible independently of A's.
        ta = threading.Thread(target=writer, args=("A", 1))
        tb = threading.Thread(target=writer, args=("B", 2))
        ta.start()
        tb.start()
        if not (inserted["A"].wait(timeout=60) and inserted["B"].wait(timeout=60)):
            errors.append("main: writers did not reach uncommitted state")

        if not errors:
            results["reader1_uncommitted_invisible"], snap1 = read_count()
            results["reader1_snapshot"] = snap1
            release["A"].set()
            ta.join(timeout=60)
            cnt2, snap2 = read_count()
            results["reader2_after_a_commit_only"] = cnt2
            results["reader2_snapshot"] = snap2
            release["B"].set()
            tb.join(timeout=60)
            with psycopg.connect(dsn) as rconn3:
                with rconn3.cursor() as cur:
                    cur.execute(
                        "SELECT id, writer FROM research_test.commit_visibility ORDER BY id"
                    )
                    results["rows_after_both_commits"] = [
                        [r[0], r[1]] for r in cur.fetchall()
                    ]

        if errors:
            evidence["errors"] = errors
            evidence["verdict"] = "FAIL_WRITE"
            json.dump(evidence, open(out_path, "w"), indent=2)
            print(json.dumps(evidence))
            return 1

        # All three observations must hold for independent commit visibility.
        verdict = (
            results["reader1_uncommitted_invisible"] == 0
            and results["reader2_after_a_commit_only"] == 1
            and results["rows_after_both_commits"] == [[1, "A"], [2, "B"]]
        )
        evidence["visibility"] = results
        evidence["verdict"] = "PASS" if verdict else "FAIL_VISIBILITY"
        evidence["concurrent_writers"] = 2
        evidence["independent_transactions"] = True

    # Input SHAs recorded for provenance (files are read-only evidence).
    evidence["inputs_sha256"] = {
        "pg_guard.py": _sha_file("/work/research/venue2027/_shared/tools/pg_guard.py"),
        "pg_concurrency_probe.py": _sha_file(
            "/work/research/venue2027/_shared/tools/pg_concurrency_probe.py"
        ),
    }
    evidence["captured_at_utc"] = os.environ.get("SOURCE_DATE_EPOCH", "runtime")
    json.dump(evidence, open(out_path, "w"), indent=2)
    print(json.dumps(evidence))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
