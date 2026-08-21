# GLHS Concurrency Repetition — Freeze Record

- **Freeze ID:** `GLHS-CONCURRENCY-REPETITION-V1-20260819`
- **Manifest:** `repeat_manifest.json` (schema `glhs-concurrency-repetition-v1`, status `FROZEN_FINAL_REVIEWED`)
- **Base protocol:** `research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json` (frozen, READ-ONLY; not modified)
- **Base run:** `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01` (12 logical schedules; canonical evidence `protocol_v2/run_v2_raw.json`, READ-ONLY)
- **Runner:** `evaluation/glhs_postgres_toctou/executor_v3.py` (delegates to `executor_v2.py` drivers — no new framework)

## Frozen parameters (spec 3.4)

| Parameter | Frozen value |
| --- | --- |
| Repetitions per logical schedule | 50 |
| Scientific N | 12 logical schedules (repetitions are robustness, NOT N — spec rule 7) |
| Jitter seed list | deterministic 50 seeds derived from `sha256(f"{FREEZE_ID}:seed:{i}")` |
| Jitter range | ±200 ms pre-barrier |
| Interleaving modes | `a_first`, `b_first`, `randomized` |
| DB isolation level | `read committed` |
| Lock timeout | 10 000 ms |
| Statement timeout | 30 000 ms |
| `track_commit_timestamp` availability | probed at run time (server-level setting; recorded honestly) |
| Observer schema version | `glhs-postgres-governance-toctou-final-v2` |
| Ordering confidence enum | `DIRECT_ORDER_EVIDENCE`, `PARTIAL`, `INDETERMINATE` |

## Aggregation rule (spec 3.4 / GLHS-C04)

- A schedule is **robust only if ALL 50 repetitions satisfy the invariant**.
- Mixed classifications are **reported**, never majority-voted into safety.
- Deadlock / serialization failure / lock timeout are **operational outcomes,
  never safety successes**.
- Commit order is **never inferred from txid numeric order alone** (spec 3.5);
  without durable `pg_xact_commit_timestamp` evidence the ordering confidence
  is `INDETERMINATE`, recorded honestly.

## Execution status

**STATUS: EXECUTED.**

- **Run ID:** `GLHS-CONCURRENCY-REPETITION-V1-20260819-RUN01`
- **Execution timestamp:** `2026-08-19T08:38:58.493508+00:00`
- **Code revision SHA:** `383c6df2`
- **Backend:** `isolated_postgresql_random_schema` (isolated research PostgreSQL with dynamic schema creation/drop)
- **Commit timestamp instrumentation:** `track_commit_timestamp = on` (`durable_commit_timestamps_available`)
- **Total executions:** 600 runs (12 logical schedules × 50 deterministic repetitions each)
- **Scientific N:** 12 logical schedules (repetitions are robustness executions, NOT new scientific N)

### Robustness & classification findings

| Category | Count | Schedule IDs / Distributions |
| --- | --- | --- |
| Robust schedules (50/50 satisfy invariant) | 10 | `TOCTOU-V2-01`, `TOCTOU-V2-02`, `TOCTOU-V2-03`, `TOCTOU-V2-04`, `TOCTOU-V2-06`, `TOCTOU-V2-07`, `TOCTOU-V2-08`, `TOCTOU-V2-10`, `TOCTOU-V2-11`, `TOCTOU-V2-12` |
| Nonrobust schedules (mismatch expected) | 2 | `TOCTOU-V2-05` (50 rejected vs expected indeterminate), `TOCTOU-V2-09` (34 committed, 14 rejected, 2 indeterminate vs expected indeterminate) |
| Mixed classifications | 0 | None majority-voted into safety; all raw distributions preserved |
| Operational failures (deadlock/timeout) | 0 | 0 across all 600 runs |
| Ordering confidence | 600 | `PARTIAL: 600` (captured commit metadata & transaction traces; no txid numeric order inference) |

### Sealed output artifacts

- `repeat_raw.jsonl`: SHA-256 `f98ce492e54a4478d929a0b8a7e800929e3c7a9b6316d4acca07d04ca77357a5`
- `analysis.json`: SHA-256 `877da64356bb37bd8e7bb66ef937004ab86d988d019b83eab3c5a404ed18728a`
- `repeat_manifest.json`: SHA-256 `4b66c774bb8f16bbb697d0efc1c1da69953ffbb2b7521602cae9accd12a5e62e`
- `seal/seal.json` + `seal/artifact-sha256.json`

## No-tamper statements

- `protocol_v2/**` was NOT modified (read-only canonical evidence).
- No existing sealed run was overwritten.
- No repetition is counted as new scientific N.
