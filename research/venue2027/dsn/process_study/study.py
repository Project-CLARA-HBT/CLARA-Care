"""Run from the repository root via run.sh. Output must be a fresh directory."""

import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import psycopg

from evaluation.venue2027.dsn import candidate as b3
from research.venue2027.dsn.process_study.worker import chain, intent

CUTS = (
    "clean",
    "producer_open",
    "decision_durable",
    "before_dispatch",
    "consumer_open",
    "sink_committed",
    "ack_durable",
)
PAYLOAD = "hotel-01/flight-02"
DIGEST = hashlib.sha256(PAYLOAD.encode()).hexdigest()
MODULE = "research.venue2027.dsn.process_study.worker"


def launch(arm, cut, op):
    start = time.monotonic_ns()
    try:
        result = subprocess.run(
            [sys.executable, "-m", MODULE, arm, cut, op], timeout=10, capture_output=True, text=True
        )
        exit_code, marker, error = result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        exit_code, marker, error = None, "", "timeout"
    return dict(
        code=exit_code, marker=marker, error=error, elapsed_ms=(time.monotonic_ns() - start) / 1e6
    )


def observe(db, sink, arm, op):
    # Full scans on a fresh history expose wrong-key and extra rows.
    reservation = db.execute("select op,payload from reservation").fetchall()
    message = db.execute("select op,payload,ack from outbox").fetchall()
    orders = sink.execute("select op,payload from orders order by id").fetchall()
    processed = sink.execute("select op from processed").fetchall()
    if arm in {"journal", "confirmed"}:
        journal = chain(db, op)
        status = b3.recoverable_outcome(journal, intent(op)).reason_code
        entries = db.execute("select op,entry from journal order by seq").fetchall()
        receipts = [
            (key, entry["payload"].get("payload_digest_sha256"))
            for key, entry in entries
            if entry["kind"] == "COMMIT"
        ]
    else:
        receipts = db.execute("select op,digest from receipt").fetchall()
        status = (
            "APPLIED" if any(row[2] for row in message) else "PENDING" if receipts else "ABSENT"
        )
    applied = status in ("APPLIED", "COMMITTED_EFFECT_APPLIED")
    complete = (
        reservation == [(op, PAYLOAD)]
        and receipts == [(op, DIGEST)]
        and message == [(op, PAYLOAD, True)]
        and orders == [(op, PAYLOAD)]
        and processed == [(op,)]
        and applied
    )
    return dict(
        reservation=reservation,
        receipt=receipts,
        message=message,
        processed=processed,
        orders=orders,
        status=status,
        complete=complete,
        false_applied=applied and orders != [(op, PAYLOAD)],
    )


def setup(db, sink):
    db.execute("create table reservation(op text primary key,payload text not null)")
    db.execute("create table receipt(op text primary key,digest text not null)")
    db.execute(
        "create table outbox(op text primary key,payload text not null,ack boolean not null)"
    )
    db.execute("create table journal(op text,seq int,entry jsonb not null,primary key(op,seq))")
    sink.execute("create table processed(op text primary key)")
    sink.execute(
        "create table orders(id bigserial primary key,op text not null,payload text not null)"
    )


def study(out, repair=False):
    out.mkdir(parents=True, exist_ok=False)
    with psycopg.connect(dbname="postgres", autocommit=True) as admin:
        for name in ("source", "sink"):
            admin.execute(f"create database {name}")
    registered = ("atomic", "journal", "confirmed") if repair else ("atomic", "journal")
    counts = {arm: Counter() for arm in registered}
    with (
        psycopg.connect(dbname="source", autocommit=True) as db,
        psycopg.connect(dbname="sink", autocommit=True) as sink,
        (out / "histories.jsonl").open("x") as log,
    ):
        setup(db, sink)
        settings = {
            k: db.execute(f"show {k}").fetchone()[0]
            for k in ("server_version", "fsync", "synchronous_commit")
        }
        assert settings["fsync"] == settings["synchronous_commit"] == "on"
        for repetition in range(3):
            arms = (
                registered[repetition % len(registered) :]
                + registered[: repetition % len(registered)]
            )
            for cut in CUTS:
                op = f"booking-{repetition}-{cut}"
                for arm in arms:
                    db.execute("truncate reservation, receipt, outbox, journal")
                    sink.execute("truncate orders, processed")
                    first = launch(arm, cut, op)
                    before = observe(db, sink, arm, op)
                    replay = launch(arm, "clean", op)
                    after = observe(db, sink, arm, op)
                    target = (0, "") if cut == "clean" else (-signal.SIGKILL, cut)
                    failed = (first["code"], first["marker"]) != target or replay["code"] != 0
                    record = dict(
                        arm=arm,
                        cut=cut,
                        repetition=repetition,
                        first=first,
                        before=before,
                        replay=replay,
                        after=after,
                        execution_error=failed,
                    )
                    print(json.dumps(record), file=log, flush=True)
                    counts[arm].update(
                        histories=1,
                        execution_errors=int(failed),
                        primary_losses=int(failed or not after["complete"]),
                        false_applied=int(before["false_applied"]),
                    )
    manifest = dict(
        counts=counts,
        settings=settings,
        python=platform.python_version(),
        psycopg=psycopg.__version__,
        postgres_image=os.environ["STUDY_IMAGE"],
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        protocol_commit="e826954b" if repair else "b85e8e6d",
        histories_sha256=hashlib.sha256((out / "histories.jsonl").read_bytes()).hexdigest(),
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(counts))


if __name__ == "__main__":
    study(Path(sys.argv[1]), repair=os.environ.get("STUDY_REPAIR") == "1")
