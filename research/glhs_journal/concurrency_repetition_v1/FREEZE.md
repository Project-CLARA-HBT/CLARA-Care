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

**STATUS: NOT EXECUTED — PENDING.**

PostgreSQL was **not reachable** during this freeze (no running isolated
research PostgreSQL; `docker` unavailable in the working environment; no
`GLHS_TOCTOU_FINAL_DATABASE_URL`). Per the fail-closed contract, **no results
were fabricated** and no `repeat_raw.jsonl` / `analysis.json` were emitted.

To execute after an operator provisions the isolated research PostgreSQL:

```bash
export GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH=1
export GLHS_TOCTOU_FINAL_DATABASE_URL="postgresql+psycopg://USER:PASS@HOST:PORT/glhs_repeat_research_db"
services/api/.venv/bin/python -m evaluation.glhs_postgres_toctou.executor_v3 \
  --protocol research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json \
  --manifest research/glhs_journal/concurrency_repetition_v1/repeat_manifest.json \
  --output-dir research/glhs_journal/concurrency_repetition_v1
```

The runner refuses non-isolated/shared databases and non-frozen protocols or
manifests. Post-execution, `repeat_raw.jsonl` (50 × 12 records) and
`analysis.json` (schedule-level robustness + ordering-confidence distribution)
must be committed with their checksums and this freeze updated to
`EXECUTED`, or this record stays `PENDING` — it is never claimed as evidence.

## No-tamper statements

- `protocol_v2/**` was NOT modified (read-only canonical evidence).
- No existing sealed run was overwritten.
- No repetition is counted as new scientific N.
