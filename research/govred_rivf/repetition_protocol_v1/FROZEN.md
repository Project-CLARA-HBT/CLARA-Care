# GovRed repetition protocol v1 (E-002 / E-003) — FROZEN, PENDING EXECUTION

GRD-02: instrument concurrency with persistent transaction/ordering evidence,
repeat with jitter, and reclassify an INDETERMINATE schedule only when ordering
is directly supported by the frozen observer contract. GLHS spec §3.4/§3.5
govern the frozen repetition manifest and the commit-order evidence rules.

## Scope

- Family: `concurrent_stale_state_write` — the sole GLHS_STRICT primary
  residual family in final-003 (30/30 residuals, `INDETERMINATE_ORDERING`).
- 30 logical scenarios (`concurrent_stale_state_write-001` … `-030`).
- **50 repetitions per scenario**, 1,500 repetitions total.
- The logical unit is the **scenario**: repetitions never increase N. A
  schedule is robust only if *all* valid repetitions satisfy the invariant;
  mixed classifications are reported explicitly, never majority-voted into
  safety (`govred_repetition_protocol.aggregate_at_logical_schedule`).

## Frozen manifest fields (GLHS spec §3.4)

`repeat_manifest.json` (`govred-repetition-protocol-v1`, status `frozen`):

- `repetitions_per_logical_schedule` = 50
- jitter range = [5.0, 50.0] ms; jitter seed list = [20260818, 20260819,
  20260820, 20260821] (one seed per repetition block)
- interleaving modes = `simultaneous_release`, `governance_first`,
  `commit_first`
- DB isolation level = `READ_COMMITTED`; lock timeout = 30 s; statement
  timeout = 30 s
- `track_commit_timestamp_available` = true (isolated research PostgreSQL only)
- observer schema = `glhs-postgres-governance-toctou-final-v2.1`

Per repetition the record carries: `schedule_id`, `repeat_id`, governance and
proposal txids, backend PID, barrier timestamps, lock waits, writer commit
metadata, proposal commit metadata, audit/reconstruction outcome, and the
ordering confidence + reason.

## Commit-order evidence (GLHS spec §3.5)

- Enable `track_commit_timestamp=on` in the **isolated research PostgreSQL
  only** (never production). Retrieve `pg_xact_commit_timestamp(txid)` for both
  transactions **after both complete**.
- **Transaction ID numeric order is never used** to infer commit order
  (`ORDER_UNKNOWABLE` unless DB commit timestamps or frozen monotonic observer
  events resolve the order).
- If database-level order remains unknowable for a repetition, the repetition
  is `INDETERMINATE` — regardless of whether the commit occurred.
- Monotonic barrier/observer evidence may corroborate only when conclusive
  (governance commit observed before proposal start, or proposal completion
  observed before governance commit); overlapping windows stay INDETERMINATE.

## Status: FROZEN — PENDING EXECUTION (honest)

`PENDING.json` records: **no reachable isolated PostgreSQL on this host
(docker unavailable)**. The protocol is frozen and marked pending rather than
fabricating outcomes. Execution requires:

1. an operator-owned `govred-isolated` compose stack (or equivalent isolated
   PostgreSQL) with `track_commit_timestamp=on`;
2. `GOVRED_REPETITION_ISOLATED_RESEARCH=1` and a
   `GOVRED_REPETITION_DATABASE_URL` (fail-closed gate in
   `govred_repetition_protocol.require_isolated_postgres`);
3. the real DB-backed scenario driver (concurrency runner wired to the
   persisted governance writers + GLHS gateway).

No execution is claimed here; no INDETERMINATE schedule has been reclassified.