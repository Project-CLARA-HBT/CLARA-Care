# LifeMap outbox worker runbook

Owner: Platform/SRE
Safety owner: Clinical Safety
Status: operational baseline; V2 feature flags remain off

## Runtime

The API commits canonical changes and `lifemap_outbox_events` in one
transaction. Only the standalone `lifemap-worker` may deliver those events.
API replicas must not run an in-process relay.

Readiness is `GET /health/ready` on loopback port 8020. It becomes ready only
after a database/outbox cycle succeeds. Liveness is `GET /health/live`.

Workers claim FIFO batches with PostgreSQL `FOR UPDATE SKIP LOCKED`, an
owner-scoped lease, bounded exponential retry, and terminal dead-letter state.
Scaling is horizontal; every replica must have a unique worker ID. Increase
replicas before batch size. Never lower the lease below the maximum observed
publisher duration.

## No-PII monitoring

Alert only on aggregate operational fields:

- oldest unpublished age;
- pending, processing, retry, dead-letter, and resolved counts;
- expired leases and retry rate;
- cycle duration and published count.

Do not put profile identifiers, event identifiers, aggregate identifiers,
payloads, clinical text, medication lists, names, or emails in metrics or
alerts. The admin health endpoint is role-gated and returns aggregate counts.

Initial operational thresholds:

- page when readiness fails for 5 minutes;
- page when any dead letter remains unresolved for 15 minutes;
- warn when oldest unpublished age exceeds 5 minutes;
- warn when retry rows increase for three consecutive checks.

These are operational defaults, not GA SLO approval.

## Incident response

1. Pause rollout flags that create the affected event class. Do not delete
   canonical rows or outbox rows.
2. Check worker readiness, database connectivity, oldest unpublished age, retry
   count, and dead-letter count.
3. If a dependency is down, restore it and allow bounded retries. Do not bulk
   replay while the dependency remains unhealthy.
4. For dead letters, inspect the no-PHI admin list. Replay or resolve only with
   admin auditing enabled and a bounded reason code.
5. Confirm pending/retry/dead-letter counts return to baseline and review logs
   for traceback/fatal/panic entries.
6. Record the event class, counts, timestamps, configuration, and corrective
   action without copying payloads into the incident record.

## Recovery and validation

Run the isolated PostgreSQL concurrency contract:

```bash
LIFEMAP_TEST_POSTGRES_URL="$DATABASE_URL" \
ALLOW_LIFEMAP_POSTGRES_CONCURRENCY_TEST=true \
python services/api/tests/integration/test_lifemap_outbox_postgres.py
```

The test creates and drops a random schema. Never point a modified copy at
application tables.

Recovery acceptance:

- concurrent claims are disjoint and complete;
- an unexpired lease cannot be stolen;
- one expired lease is reclaimed exactly once;
- duplicate drain does not republish a completed row;
- publisher failure enters retry and eventually dead-letter state;
- audited replay resets its retry budget;
- worker restart drains committed pending rows;
- aggregate health contains no payload or clinical text.

Before increasing worker replicas, run a production-like soak using an isolated
database/schema, record throughput and p95/p99 cycle duration, crash workers
during publish, and verify reconciliation. A short functional concurrency test
does not satisfy the soak or GA certification gate.

## Rollback

Set the LifeMap V2/AI producer flags off first. Scale `lifemap-worker` to zero
only after producers are paused or when stopping delivery is the safer incident
action. Existing outbox rows are durable and must remain for later recovery.
Rollback must never truncate the outbox or rewrite canonical health history.
