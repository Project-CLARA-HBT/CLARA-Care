# GLHS Concurrency Repetition V1

This directory contains the frozen repetition manifest and, only after a real
isolated PostgreSQL execution, its raw and schedule-level analysis outputs.
The runner delegates all schedule behavior to `executor_v2.py` and does not
modify `protocol_v2/**` or sealed evidence.

## Frozen Contract

- 12 logical schedules; scientific `N` remains 12.
- 50 deterministic repetitions per schedule.
- Deterministic pre-barrier jitter and the frozen `a_first`, `b_first`, and
  `randomized` interleaving modes.
- `read committed`, 10-second lock timeout, and 30-second statement timeout.
- Transaction IDs, backend PIDs, monotonic traces, lock waits, barrier/jitter
  timestamps, and durable commit timestamps where PostgreSQL supports them.
- Ordering is explicitly `DIRECT_ORDER_EVIDENCE`, `PARTIAL`, or
  `INDETERMINATE`; transaction-ID numeric order is never used.
- Deadlocks, serialization failures, and lock timeouts are operational failures,
  never safety successes. A schedule is robust only when all 50 repetitions
  satisfy its frozen invariant.

## Execution Status

`FREEZE.md` is the authoritative status record. If isolated PostgreSQL is not
reachable, the study remains `PENDING` and no repeat result is emitted.

## Manual Holdout

The independent human GLHS contract holdout required by R3 GLHS-H01/H02 is
manual and is not simulated by this runner or by an LLM. It remains pending
until an independent author freezes and executes the cases.
