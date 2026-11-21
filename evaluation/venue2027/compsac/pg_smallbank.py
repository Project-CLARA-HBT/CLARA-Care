"""Execute the three pinned BenchBase-derived procedures on a private PG socket.

Upstream license and procedure notices: research/venue2027/compsac/smallbank/.
"""

import argparse
import gzip
import hashlib
import json
import platform
import random
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter_ns

import psycopg
from psycopg import sql

SOURCE = Path(__file__).resolve().parents[3] / "research/venue2027/compsac/smallbank"
ARMS = ("ssi", "scoped_rc")


class InsufficientSavings(Exception):
    pass


def procedure(conn, arm, kind, account, reads):
    row = conn.execute("SELECT * FROM accounts WHERE name=%s", (f"{account:064d}",)).fetchone()
    (key, _) = row
    if kind == "deposit":
        conn.execute("UPDATE checking SET bal=bal+%s WHERE custid=%s", (1.3, key))
        return

    lock = ""
    if arm == "scoped_rc":
        lock = " FOR UPDATE" if kind == "withdraw" else " FOR SHARE"
    savings = conn.execute("SELECT bal FROM savings WHERE custid=%s" + lock, (key,)).fetchone()[0]
    reads.append(savings)
    if kind == "withdraw":
        if savings - 20.2 < 0:
            raise InsufficientSavings
        conn.execute("UPDATE savings SET bal=bal-%s WHERE custid=%s", (20.2, key))
        return

    lock = " FOR UPDATE" if arm == "scoped_rc" else ""
    checking = conn.execute("SELECT bal FROM checking WHERE custid=%s" + lock, (key,)).fetchone()[0]
    reads.append(checking)
    debit = 4 if checking + savings < 5 else 5
    conn.execute("UPDATE checking SET bal=bal-%s WHERE custid=%s", (debit, key))


def shard(conn, arm, ops, barrier):
    events = []
    barrier.wait()
    for kind, account in ops:
        start = perf_counter_ns()
        failures = []
        for _ in range(3):
            reads = []
            try:
                with conn.transaction():
                    procedure(conn, arm, kind, account, reads)
                status = "committed"
                break
            except InsufficientSavings:
                status = "insufficient"
                break
            except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected) as exc:
                failures.append(exc.sqlstate)
        else:
            status = "aborted"
            reads = []
        events.append(
            dict(
                kind=kind,
                account=account,
                status=status,
                failures=failures,
                reads=reads,
                start=start,
                end=perf_counter_ns(),
            )
        )
    return events


def balances(conn):
    return conn.execute(
        "SELECT s.custid,s.bal,c.bal FROM savings s JOIN checking c USING(custid) ORDER BY s.custid"
    ).fetchall()


def campaign(admin, pool, workers, arm, seed, accounts):
    admin.execute("TRUNCATE checking,savings,accounts")
    admin.execute(
        "INSERT INTO accounts SELECT i,lpad(i::text,64,'0') FROM generate_series(0,%s) i",
        (accounts - 1,),
    )
    admin.execute("INSERT INTO checking SELECT custid,0 FROM accounts")
    admin.execute("INSERT INTO savings SELECT custid,40.4 FROM accounts")
    for table in ("accounts", "savings", "checking"):
        admin.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))
    level = "serializable" if arm == "ssi" else "read committed"
    for conn in workers:
        conn.execute(sql.SQL("SET default_transaction_isolation TO {}").format(sql.Literal(level)))
        with conn.transaction():
            assert conn.execute("SHOW transaction_isolation").fetchone() == (level,)
    rng = random.Random(seed)
    kinds = ["check"] * 120 + ["deposit"] * 84 + ["withdraw"] * 36
    rng.shuffle(kinds)
    ops = [(k, rng.randrange(accounts)) for k in kinds]
    initial = balances(admin)
    waves = []
    for i in range(0, len(ops), 4):
        clock = []
        barrier = threading.Barrier(
            len(workers), action=lambda clock=clock: clock.append(perf_counter_ns()), timeout=30
        )
        jobs = [
            pool.submit(shard, conn, arm, ops[i : i + 4][j :: len(workers)], barrier)
            for j, conn in enumerate(workers)
        ]
        # Restore stream order so that the same four requests have stable identities across arms.
        groups = [job.result() for job in jobs]
        events = [groups[j % len(groups)][j // len(groups)] for j in range(4)]
        waves.append(
            dict(
                events=events,
                elapsed_ns=max(e["end"] for e in events) - clock[0],
                after=balances(admin),
            )
        )
    return dict(
        arm=arm, seed=seed, accounts=accounts, workers=len(workers), initial=initial, waves=waves
    )


def run(socket):
    if not socket.is_absolute() or not (socket / ".s.PGSQL.5432").is_socket():
        raise ValueError("pass the absolute private socket directory")
    dsn = dict(host=str(socket), port=5432, dbname="postgres", user="postgres", autocommit=True)
    schema = sql.Identifier("smallbank_" + uuid.uuid4().hex)
    path = sql.SQL("SET search_path TO {}").format(schema)
    with psycopg.connect(**dsn) as admin:
        if (
            admin.info.server_version != 160004
            or admin.execute("SHOW listen_addresses").fetchone()[0]
        ):
            raise ValueError("expected socket-only PostgreSQL 16.4")
        settings = {
            k: admin.execute(sql.SQL("SHOW {}").format(sql.Identifier(k))).fetchone()[0]
            for k in ("server_version", "fsync", "synchronous_commit", "shared_buffers")
        }
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        try:
            admin.execute(path)
            admin.execute((SOURCE / "schema.sql").read_text())
            with ExitStack() as stack, ThreadPoolExecutor(4) as pool:
                conns = [stack.enter_context(psycopg.connect(**dsn)) for _ in range(4)]
                for conn in conns:
                    conn.execute(path)
                rows = [
                    campaign(admin, pool, conns[:n], arm, seed, accounts)
                    for accounts in (4, 32)
                    for n in (1, 4)
                    for seed in range(6)
                    for arm in (ARMS if seed % 2 == 0 else reversed(ARMS))
                ]
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))
    return dict(
        settings=settings,
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        upstream="33c00473807ebd49304d114a6d769d2d2b2bbb34",
        kernel=platform.release(),
        python=sys.version,
        driver=psycopg.__version__,
        rows=rows,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evidence = run(args.socket)
    with gzip.open(args.output, "xt", encoding="utf-8") as stream:
        json.dump(evidence, stream, separators=(",", ":"))
