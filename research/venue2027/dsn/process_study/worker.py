"""Single-worker PostgreSQL port of the registered, successful reservation slice."""

import hashlib
import os
import signal
import sys

import psycopg
from psycopg.types.json import Jsonb

from evaluation.venue2027.dsn import candidate as b3

PAYLOAD = "hotel-01/flight-02"
DIGEST = hashlib.sha256(PAYLOAD.encode()).hexdigest()


def intent(op):
    return b3.WriteIntent(op, "demo", "worker", "reserve", 1, DIGEST, 0)


def chain(db, op):
    rows = db.execute("select entry from journal where op=%s order by seq", (op,))
    return b3.SafetyJournal(b3.JournalEntry.from_dict(row[0]) for row in rows)


def checkpoint(cut, here):
    if cut == here:
        print(here, flush=True)
        os.kill(os.getpid(), signal.SIGKILL)


def insert_reservation(db, op):
    db.execute("insert into reservation values (%s,%s) on conflict do nothing", (op, PAYLOAD))


def enqueue(db, op):
    db.execute("insert into outbox values (%s,%s,false) on conflict do nothing", (op, PAYLOAD))


def produce_atomic(db, op, cut):
    with db.transaction():
        insert_reservation(db, op)
        checkpoint(cut, "producer_open")
        db.execute("insert into receipt values (%s,%s) on conflict do nothing", (op, DIGEST))
        enqueue(db, op)
    checkpoint(cut, "decision_durable")


def append(db, journal, op, kind, payload):
    if any(entry.kind == kind for entry in journal.entries):
        return journal
    journal = journal.append(kind, op, payload, len(journal))
    entry = journal.entries[-1]
    db.execute("insert into journal values (%s,%s,%s)", (op, entry.seq, Jsonb(entry.to_dict())))
    return journal


def produce_journal(db, op, cut):
    journal = chain(db, op)
    if b3.verify_journal(journal, op):
        raise ValueError("invalid durable journal")
    journal = append(
        db,
        journal,
        op,
        b3.INTENT,
        {
            "payload_digest_sha256": DIGEST,
            "authorized_consent_epoch": 1,
        },
    )
    with db.transaction():
        journal = append(
            db,
            journal,
            op,
            b3.COMMIT,
            {
                "payload_digest_sha256": DIGEST,
                "consent_epoch_at_commit": 1,
                "row_version": 1,
            },
        )
        checkpoint(cut, "producer_open")
    checkpoint(cut, "decision_durable")
    insert_reservation(db, op)
    with db.transaction():
        append(db, journal, op, b3.OUTBOX_RECORD, {})
        enqueue(db, op)


def record_applied(db, key):
    append(
        db,
        chain(db, key),
        key,
        b3.EFFECT_APPLIED,
        {
            "attempt": 1,
            "effect_receipt_digest": b3._effect_digest(key),
        },
    )


def consume(sink, op, payload, cut):
    with sink.transaction():
        accepted = sink.execute(
            "insert into processed values (%s) on conflict do nothing returning op", (op,)
        ).fetchone()
        if accepted:
            sink.execute("insert into orders(op,payload) values (%s,%s)", (op, payload))
            checkpoint(cut, "consumer_open")


def run(arm, cut, op):
    with (
        psycopg.connect(dbname="source", autocommit=True) as db,
        psycopg.connect(dbname="sink", autocommit=True) as sink,
    ):
        if arm in {"journal", "confirmed"}:
            produce_journal(db, op, cut)
        else:
            produce_atomic(db, op, cut)
        checkpoint(cut, "before_dispatch")
        # Scan durable pending work. Relay only acknowledges after the independent sink commits.
        for key, payload in db.execute("select op,payload from outbox where not ack").fetchall():
            if arm == "journal":
                record_applied(db, key)
            for _ in range(2):
                consume(sink, key, payload, cut)
                checkpoint(cut, "sink_committed")
            with db.transaction():
                if arm == "confirmed":
                    record_applied(db, key)
                db.execute("update outbox set ack=true where op=%s", (key,))
            checkpoint(cut, "ack_durable")


if __name__ == "__main__":
    run(*sys.argv[1:])
