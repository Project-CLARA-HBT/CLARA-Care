# Atomic outbox and journal recovery after worker termination

**Retire the primary superiority claim.** Both the atomic outbox and the journal recovered every operation across the six kill positions and the clean control. A separate readback found a journal-specific error during the outage. At the consumer-open boundary, the journal claimed a completed delivery while PostgreSQL had rolled back the order insert. The outbox still showed a pending message. Across three repeat executions of this schedule the difference was reproducible in each of the two original archives.

The engineering repair moves the effect-applied marker into the source acknowledgment transaction after the idempotent sink commits. In the three-arm repeat all 63 histories completed with correct reservation, receipt, message, consumer key and exactly one order after recovery. Before recovery the original journal made three premature claims. The repaired journal and ordinary outbox each made zero. These are deterministic schedules on an adapted reservation workflow, with application processes killed and the PostgreSQL server surviving. They measure an observable status bug and its repair. No superiority over the outbox remains on either registered endpoint.

From the repository root, verify the hashes, grid, termination signals, row and receipt identities and replay outcomes. Each JSONL retains before/after readbacks. A local PostgreSQL container supplies an isolated fresh run.
```sh
p=research/venue2027/dsn/process_study
python "$p/verify.py" "$p/results/original" "$p/results/retry" "$p/results/confirmed-dev"
STUDY_REPAIR=1 "$p/run.sh" /tmp/dsn-new-output
```

[Registered elimination and repair decisions](protocol.md) · [Three-arm manifest](results/confirmed-dev/manifest.json) · [Reference implementation](worker.py)
