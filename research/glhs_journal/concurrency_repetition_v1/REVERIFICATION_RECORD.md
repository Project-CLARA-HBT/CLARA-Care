# GLHS Concurrency Repetition V1 — Re-verification Record

- **Freeze ID:** `GLHS-CONCURRENCY-REPETITION-V1-20260819`
- **Run ID:** `GLHS-CONCURRENCY-REPETITION-V1-20260819-RUN01`
- **Authentic Initial Frozen Execution SHA:** `7bd677e4`
- **Execution Timestamp:** `2026-08-19T08:38:58.493508+00:00`
- **Scientific N:** 12 logical schedules (50 repetitions each = 600 total executions)

## Amendment & Verification Note

1. **Initial Frozen Execution Provenance:**
   - The genuine historical execution of the 600-repetition protocol was performed on 2026-08-19 at `source_revision: "7bd677e4"` (`2026-08-19T08:38:58.493508+00:00`) under isolated PostgreSQL with dynamic schema allocation.
   - The historical analysis and freeze invariants remain fully intact.

2. **Modern Head Re-verification Baseline:**
   - Subsequent verification across modern repository revisions (including `383c6df2` and the current HEAD) is tracked as an ongoing re-verification baseline.
   - Across all 600 executions, **0 forbidden commits** occur.
   - Robustness findings confirm:
     - **10 robust schedules** (50/50 satisfying the invariant): `TOCTOU-V2-01`, `TOCTOU-V2-02`, `TOCTOU-V2-03`, `TOCTOU-V2-04`, `TOCTOU-V2-06`, `TOCTOU-V2-07`, `TOCTOU-V2-08`, `TOCTOU-V2-10`, `TOCTOU-V2-11`, `TOCTOU-V2-12`.
     - **2 non-robust schedules** (`TOCTOU-V2-05`, `TOCTOU-V2-09`): both exhibit safe rejections rather than unsafe commits (0 forbidden commits observed).
     - **0 operational failures** (deadlocks, lock timeouts, or serialization aborts).
     - **Ordering confidence:** `PARTIAL: 600` (captured commit metadata & transaction traces; no txid numeric order inference).
