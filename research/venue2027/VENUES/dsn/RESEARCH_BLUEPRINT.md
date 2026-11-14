# DSN · independently executable study implementation book

**Paper:** Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations

**Proposed contribution:** Recoverability is a safety property of the *joint* clinical row, immutable decision lineage, and asynchronous side-effect record, not just of one database commit. Define a recoverable outcome function that returns COMMITTED, REJECTED, or INDETERMINATE until reconcilable ground truth exists.

**Literature gap and competing explanation:** Transactional outbox and database WAL already give crash-safe writes; the unresolved issue worth testing is whether an AI proposal lineage and user-visible decision stay consistent across crash windows and arbitrary duplicate deliveries. Without a new counterexample to a careful outbox baseline, this is an application paper, not a DSN A contribution.

**Three research questions**

**RQ1: Across crash cut points, are there executions where the clinical state, decision receipt, and outbox state disagree after bounded recovery?**
**RQ2: Under at-least-once replay and concurrent consent revocation, does recovery preserve idempotence, causal order, and correct INDETERMINATE labels?**
**RQ3: What is the added durable-write, p99 latency and recovery-time cost compared with transactional outbox and durable workflow baselines?**

**Falsification criterion:** If a correctly engineered PostgreSQL transaction + outbox + idempotent consumer achieves the same invariants and equal/better recovery cost, discard the new mechanism superiority claim.

**Method architecture:** A reconciler checks a versioned decision receipt against the committed row, independent outbox receipt and consent epoch. Invalid/ambiguous evidence never becomes a positive outcome; retry decisions are keyed to immutable operation IDs.

**Planned study population / resources:** Generate 48 crash windows x 4 commit/revocation orderings x 3 delivery schedules x 5 independent seeds. Confirm final N only after schedule deduplication; benchmark 1/2/4/8 worker settings.

**Independent oracle:** Jepsen/Elle-compatible history export plus deterministic SQL-state audit; manually review anomaly witnesses.

**Required metrics:** orphan clinical writes per independent history, phantom user-visible success, eventual safe reconciliation fraction, duplicate side effects, RTO p50/p95/p99, extra fsyncs per operation

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | DB transaction only + fire-and-forget side effect | weak control; measures lost side effects |
| B1 | PostgreSQL atomic write + transactional outbox + idempotent consumer | strong practical baseline; must implement fully |
| B2 | Durable workflow/saga with compensation and stable operation IDs | strong operational baseline; record precise engine/version |
| B3 | Proposed reconciliation safety journal | candidate; no pre-existing performance assumed |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 4 tasks; see `PHASES/P03.md`.
- `P04`: 4 tasks; see `PHASES/P04.md`.
- `P05`: 5 tasks; see `PHASES/P05.md`.
- `P06`: 3 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue dsn` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/dsn/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
