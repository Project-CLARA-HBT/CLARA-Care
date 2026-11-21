# PostgreSQL development results

Each cell compares six target-order seeds on PostgreSQL 16.4. Each seed ran native serializable snapshot isolation (SSI), exclusive dependency locks and shared dependency locks in balanced arm order. Each campaign scheduled 96 proposals on disjoint targets, including 12 carrying an ineligible dependency version. The two ratio columns give the median of the six within-seed committed-throughput ratios to SSI. A ratio below one favors SSI. W counts proposal workers and F counts shared dependencies.

## v1

Separate read and write statements, one table, zero retries. [Campaign records](../proof/artifacts/compsac_pg_scope_dev_v1.json)

| W | F | Exclusive / SSI | Shared / SSI | SSI commits/s¹ | Retries² | Missing eligible² | Forbidden installs² |
|---:|---:|---:|---:|---:|---|---|---|
| 1 | 1 | 1.08 | 0.96 | 295.6 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 1 | 8 | 0.90 | 0.93 | 319.9 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 4 | 1 | 0.46 | 0.86 | 842.0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 4 | 8 | 0.86 | 1.97 | 385.9 | 0 / 0 / 0 | 292 / 0 / 0 | 0 / 0 / 0 |

## v2

One conditional statement for all arms, one table, zero retries. [Campaign records](../proof/artifacts/compsac_pg_scope_dev_v2.json)

| W | F | Exclusive / SSI | Shared / SSI | SSI commits/s¹ | Retries² | Missing eligible² | Forbidden installs² |
|---:|---:|---:|---:|---:|---|---|---|
| 1 | 1 | 0.89 | 0.95 | 335.7 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 1 | 8 | 0.99 | 0.98 | 328.9 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 4 | 1 | 0.53 | 0.92 | 787.3 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 4 | 8 | 0.93 | 1.59 | 492.2 | 0 / 0 / 0 | 272 / 0 / 0 | 0 / 0 / 0 |

## v3

One conditional statement, one table, fresh planner statistics and two retries. [Campaign records](../proof/artifacts/compsac_pg_scope_dev_v3.json)

| W | F | Exclusive / SSI | Shared / SSI | SSI commits/s¹ | Retries² | Missing eligible² | Forbidden installs² |
|---:|---:|---:|---:|---:|---|---|---|
| 1 | 1 | 0.89 | 0.93 | 329.2 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 1 | 8 | 0.85 | 0.88 | 309.0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 4 | 1 | 1.28 | 2.61 | 334.7 | 765 / 0 / 0 | 252 / 0 / 0 | 0 / 0 / 0 |
| 4 | 8 | 1.34 | 2.01 | 318.6 | 767 / 0 / 0 | 261 / 0 / 0 | 0 / 0 / 0 |

## v4

Separate dependency and target tables, fresh statistics and two retries. [Campaign records](../proof/artifacts/compsac_pg_scope_dev_v4.json)

| W | F | Exclusive / SSI | Shared / SSI | SSI commits/s¹ | Retries² | Missing eligible² | Forbidden installs² |
|---:|---:|---:|---:|---:|---|---|---|
| 1 | 1 | 1.01 | 1.04 | 310.6 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 1 | 8 | 0.94 | 0.97 | 328.7 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 4 | 1 | 1.04 | 2.00 | 367.3 | 753 / 0 / 0 | 234 / 0 / 0 | 0 / 0 / 0 |
| 4 | 8 | 0.94 | 1.41 | 440.3 | 704 / 0 / 0 | 204 / 0 / 0 | 0 / 0 / 0 |

## epoch

Split tables and two retries. Four dependency updates commit between proposal waves. [Campaign records](../proof/artifacts/compsac_pg_epoch_dev.json)

| W | F | Exclusive / SSI | Shared / SSI | SSI commits/s¹ | Retries² | Missing eligible² | Forbidden installs² |
|---:|---:|---:|---:|---:|---|---|---|
| 4 | 8 | 2.19 | 2.17 | 739.6 | 395 / 0 / 0 | 78 / 0 / 0 | 0 / 0 / 0 |

¹ Median across six campaigns. ² Totals over six campaigns, in SSI / exclusive / shared order. The throughput numerator counts installed proposals. Retries are additional attempts within a proposal.

Layout, statistics, retry policy and query shape changed during development. Differences across rounds combine these changes with run-to-run variation. In the epoch experiment, the writer advances all eight versions before the next wave starts. This establishes the version seen by each proposal and leaves overlap with the governance writer untested. Finite retries can reduce SSI's committed-work numerator. These campaigns estimate component behavior on a fixed workload. The registered safety and utility endpoints for the dependency-complete kernel still require independent history labels and a fresh workload.
