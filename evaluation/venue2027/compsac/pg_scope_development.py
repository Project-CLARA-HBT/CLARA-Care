"""Paired development probe on a disposable, Unix-socket-only PostgreSQL 16 cluster.

Compares native SSI with a row-lock implementation on the same restricted
workload. The workload covers disjoint target writes and shared versioned
dependencies. Both arms re-read identical dependency sets and conditionally
advance only the target version. This is a component probe, not the full B4
kernel. Results include every attempt, including server serialization aborts.

Run as a module with the private socket directory as the only argument.
Use a dedicated empty clara_research database. Tables are created under a new
schema for each invocation and removed on completion.
"""

import hashlib
import json
import random
import sys
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import permutations
from pathlib import Path
from time import perf_counter

import psycopg
from psycopg import sql

ARMS = ("ssi", "exclusive_dependencies", "shared_dependencies")
OPS = 96


def attempt(conn, arm, target, deps, expected_epoch):
    isolation = "SERIALIZABLE" if arm == "ssi" else "READ COMMITTED"
    lock = {
        "ssi": "",
        "exclusive_dependencies": " FOR UPDATE",
        "shared_dependencies": " FOR SHARE",
    }[arm]
    try:
        with conn.transaction():
            conn.execute(sql.SQL("SET TRANSACTION ISOLATION LEVEL " + isolation))
            # Reuse one materialized read set for cardinality, version checks
            # and diagnostics. Every arm gets the same SQL and round-trip count.
            statement = sql.SQL("""
                WITH observed AS MATERIALIZED (
                    SELECT version FROM evidence WHERE id = ANY(%s) ORDER BY id {}
                ), validated AS (
                    SELECT count(*) = %s AND bool_and(version = %s) AS ok FROM observed
                ), written AS (
                    UPDATE evidence SET version = 1
                    WHERE id = %s AND version = 0 AND (SELECT ok FROM validated)
                    RETURNING id
                )
                SELECT CASE WHEN EXISTS (SELECT FROM written) THEN 'committed'
                            WHEN (SELECT ok FROM validated) THEN 'stale_target'
                            ELSE 'stale_dependency' END
            """).format(sql.SQL(lock))
            return conn.execute(statement, (deps, len(deps), expected_epoch, target)).fetchone()[0]
    except psycopg.errors.SerializationFailure:
        return "serialization_abort"


def campaign(admin, dsn, schema, arm, workers, fanout, seed):
    admin.execute("TRUNCATE evidence")
    admin.execute(
        "INSERT INTO evidence SELECT i,0 FROM generate_series(1,%s) AS i", (OPS + fanout,)
    )
    admin.execute("ANALYZE evidence")
    targets = list(range(fanout + 1, fanout + OPS + 1))
    random.Random(seed).shuffle(targets)
    deps = list(range(1, fanout + 1))
    timing = {}
    start = threading.Barrier(
        workers + 1, action=lambda: timing.update(start=perf_counter()), timeout=30
    )

    def run(shard):
        with psycopg.connect(**dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            start.wait()
            counts = Counter()
            for target in shard:
                for retry in range(3):
                    outcome = attempt(conn, arm, target, deps, int(target % 8 == 0))
                    if outcome != "serialization_abort" or retry == 2:
                        break
                    counts["retries"] += 1
                counts[outcome] += 1
            return counts, perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, targets[i::workers]) for i in range(workers)]
        start.wait()
        completed = [f.result() for f in futures]
        counts = sum((count for count, _ in completed), Counter())
        seconds = max(finish for _, finish in completed) - timing["start"]
    # Ground truth follows the immutable workload labels and independently read
    # final database rows, including each known-stale operation.
    installed = {i for (i,) in admin.execute("SELECT id FROM evidence WHERE version=1")}
    valid = {t for t in targets if t % 8}
    forbidden = len(installed - valid)
    if len(installed) != counts["committed"] or sum(counts.values()) - counts["retries"] != OPS:
        raise ValueError("attempt_readback_mismatch")
    return dict(
        counts=counts,
        forbidden_installs=forbidden,
        missing_valid=len(valid - installed),
        seconds=seconds,
        committed_per_second=counts["committed"] / seconds,
    )


def main(socket):
    if not socket.is_absolute() or not (socket / ".s.PGSQL.5432").is_socket():
        raise ValueError("private_socket_required")
    dsn = dict(host=str(socket), dbname="clara_research", user="postgres")
    schema = "scope_dev_" + uuid.uuid4().hex
    rows = []
    with psycopg.connect(**dsn, autocommit=True) as admin:
        if (
            admin.execute("SHOW listen_addresses").fetchone()[0]
            or admin.info.server_version // 10000 != 16
        ):
            raise ValueError("expected_socket_only_pg16")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            admin.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            admin.execute("CREATE TABLE evidence (id int PRIMARY KEY, version int NOT NULL)")
            for workers in (1, 4):
                for fanout in (1, 8):
                    for seed in range(6):
                        arms = list(ARMS)
                        # The six permutations balance order and carryover.
                        for arm in list(permutations(arms))[seed]:
                            row = campaign(admin, dsn, schema, arm, workers, fanout, seed)
                            rows.append(
                                dict(workers=workers, fanout=fanout, seed=seed, arm=arm, **row)
                            )
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        version = admin.info.server_version
    return dict(
        scope="development_disjoint_targets_shared_dependencies",
        server_version_num=version,
        retry_limit=2,
        planner_statistics="ANALYZE after each population",
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        operations_per_campaign=OPS,
        rows=rows,
    )


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1])), indent=2))
