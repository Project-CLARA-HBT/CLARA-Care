"""Run the prespecified changing-epoch development condition on a private socket."""

import hashlib
import json
import random
import sys
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from itertools import permutations
from pathlib import Path
from time import perf_counter

import psycopg
from psycopg import sql

from . import pg_scope_development as base


def run_shard(conn, arm, epoch, targets, start):
    counts = Counter()
    start.wait()
    for target in targets:
        for n in range(3):
            outcome = base.attempt(conn, arm, target, list(range(1, 9)), epoch - (target % 8 == 0))
            if outcome != "serialization_abort" or n == 2:
                break
            counts["retries"] += 1
        counts[outcome] += 1
    return counts, perf_counter()


def campaign(admin, workers, pool, arm, seed):
    admin.execute("TRUNCATE dependencies, evidence")
    admin.execute("INSERT INTO dependencies SELECT i,0 FROM generate_series(1,8) i")
    admin.execute("INSERT INTO evidence SELECT i,0 FROM generate_series(9,104) i")
    admin.execute("ANALYZE dependencies")
    admin.execute("ANALYZE evidence")
    rng = random.Random(seed)
    waves = []
    counts = Counter()
    for epoch in range(1, 5):
        admin.execute("UPDATE dependencies SET version=version+1")
        versions = admin.execute("SELECT version FROM dependencies ORDER BY id").fetchall()
        if versions != [(epoch,)] * 8:
            raise ValueError("unexpected dependency versions")
        first = 9 + 24 * (epoch - 1)
        targets = list(range(first, first + 24))
        rng.shuffle(targets)
        clock = []
        start = threading.Barrier(
            5, action=lambda clock=clock: clock.append(perf_counter()), timeout=30
        )
        jobs = [
            pool.submit(run_shard, conn, arm, epoch, targets[i::4], start)
            for i, conn in enumerate(workers)
        ]
        start.wait()
        results = [job.result() for job in jobs]
        wave_counts = sum((c for c, _ in results), Counter())
        counts.update(wave_counts)
        waves.append(
            dict(epoch=epoch, counts=wave_counts, seconds=max(t for _, t in results) - clock[0])
        )
    installed = {i for (i,) in admin.execute("SELECT id FROM evidence WHERE version=1")}
    valid = {i for i in range(9, 105) if i % 8}
    if len(installed) != counts["committed"] or counts.total() - counts["retries"] != 96:
        raise ValueError("proposal accounting mismatch")
    seconds = sum(w["seconds"] for w in waves)
    return dict(
        arm=arm,
        workers=4,
        fanout=8,
        seed=seed,
        waves=waves,
        counts=counts,
        installed_ids=sorted(installed),
        missing_valid=len(valid - installed),
        forbidden_installs=len(installed - valid),
        seconds=seconds,
        committed_per_second=counts["committed"] / seconds,
    )


def main(socket):
    if not socket.is_absolute() or not (socket / ".s.PGSQL.5432").is_socket():
        raise ValueError("private socket required")
    dsn = dict(host=str(socket), dbname="clara_research", user="postgres", autocommit=True)
    schema = sql.Identifier("epoch_dev_" + uuid.uuid4().hex)
    search_path = sql.SQL("SET search_path TO {}").format(schema)
    with psycopg.connect(**dsn) as admin:
        if (
            admin.execute("SHOW listen_addresses").fetchone()[0]
            or admin.info.server_version != 160004
        ):
            raise ValueError("socket-only PostgreSQL 16.4 required")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        try:
            admin.execute(search_path)
            admin.execute("CREATE TABLE dependencies (id int PRIMARY KEY, version int NOT NULL)")
            admin.execute("CREATE TABLE evidence (id int PRIMARY KEY, version int NOT NULL)")
            with ExitStack() as stack, ThreadPoolExecutor(max_workers=4) as pool:
                workers = [stack.enter_context(psycopg.connect(**dsn)) for _ in range(4)]
                for conn in workers:
                    conn.execute(search_path)
                rows = [
                    campaign(admin, workers, pool, arm, seed)
                    for seed, order in enumerate(permutations(base.ARMS))
                    for arm in order
                ]
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))
    return dict(
        scope="development_changing_dependency_epochs",
        server_version_num=160004,
        operations_per_campaign=96,
        retry_limit=2,
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        base_runner_sha256=hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
        rows=rows,
    )


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1])), indent=2))
