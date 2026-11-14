# COMPSAC · independently executable study implementation book

**Paper:** Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes

**Proposed contribution:** A machine-checkable *dependency-closure oracle* for schema-defined clinical write operations, coupled with scope-local optimistic versioning that minimizes false-stale rejection without allowing write skew under changing consent and policy.

**Literature gap and competing explanation:** Silo/OCC and PostgreSQL Serializable Snapshot Isolation already address concurrency; original value must come from automatically deriving semantically required cross-resource dependencies for *AI-generated* clinical writes and quantifying the safety/throughput frontier.

**Three research questions**

**RQ1: Compared with globally versioned OCC, does a dependency-complete read set reduce unnecessary aborts without increasing forbidden commits?**
**RQ2: How does omitted dependency failure propagate under explicit write-skew and policy-epoch races, and can a separate oracle detect each flaw?**
**RQ3: At what graph fanout and contention does dependency-scope overhead erase throughput gains relative to PostgreSQL SERIALIZABLE?**

**Falsification criterion:** Any forbidden commit under a complete, independently labeled dependency schedule falsifies the safety claim; if fully serializable PostgreSQL is as fast, candidly report the null performance benefit.

**Method architecture:** Freeze per-operation dependency schema and required read/write edges. Validate all required edge versions and consent/policy epochs in one DB transaction with canonical lock ordering. Export histories to Elle/independent serializability checker.

**Planned study population / resources:** Deterministic family of medication/allergy/history/purpose grants; 1, 2, 4, 8, 16 workers; workload partitions with Zipf skew and dependency density; ≥ 5 independent seeds per setting before deciding power.

**Independent oracle:** Independent dependency oracle plus transaction-history consistency checker; record kernel SHA, PG release/version and isolation setting.

**Required metrics:** forbidden commit rate, oracle-defined false-stale rate, throughput committed ops/sec, p50/p95/p99 latency, retry amplification, dependency graph completeness

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | global-profile version OCC | common coarse implementation |
| B1 | Silo-style entity readset OCC with commit-time validation | strong algorithmic comparator; disclose that port is not Silo source code |
| B2 | PostgreSQL SERIALIZABLE (SSI) with schema-check predicates | strong DB-native comparator |
| B3 | entity-OCC without semantic dependency closure | ablation exposing write skew |
| B4 | proposed dependency-complete scope-local OCC | candidate |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 5 tasks; see `PHASES/P02.md`.
- `P03`: 5 tasks; see `PHASES/P03.md`.
- `P04`: 4 tasks; see `PHASES/P04.md`.
- `P05`: 4 tasks; see `PHASES/P05.md`.
- `P06`: 3 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 2 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue compsac` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/compsac/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
