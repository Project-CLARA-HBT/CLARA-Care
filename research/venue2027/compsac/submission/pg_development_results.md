# Disjoint-target PostgreSQL development results

On PostgreSQL 16.4, four development rounds compared native serializable snapshot
isolation (SSI) with two READ COMMITTED implementations that locked dependency rows
using FOR SHARE or FOR UPDATE. Each campaign submitted 96 proposals for distinct
targets. All proposals read the same one or eight dependency rows. Of the 96,
84 carried the current version and 12 carried a mismatched version. Each arm used
the same shuffled targets for a given seed. The six seeds covered all six arm orders.

With four workers and eight dependencies, the median shared-lock/SSI throughput
ratio was 1.968, 1.592, 2.015, 1.407 in successive rounds. With four workers and
one dependency, the corresponding ratios were 0.857, 0.916, 2.605, 1.997.
The direction of this latter comparison reversed in v3, when fresh planner
statistics and bounded retries were introduced together. In that cell SSI
left 0 valid targets uninstalled in v2 and 252
in v3. Throughput counts only installed targets, so it reflects completion as
well as elapsed time.

With four workers
and eight dependencies, the exclusive-lock median moved from
1.339 in v3 to 0.944 in v4
when dependencies and targets were placed in separate relations. With one
worker and eight dependencies, both lock arms had median ratios below one
in every round.
These are descriptive measurements of the disjoint-target validation and write
component. Full B4 and confirmatory evaluation remain outside this study.

## Paired throughput across four rounds

v1 read dependency versions and issued a separate conditional target update for
eligible proposals. v2 combined validation and the write in one SQL statement in
all three arms. Neither round retried a serialization failure. v3 added ANALYZE
after fixture population and allowed two retries per proposal. v4 retained those
settings and split the dependency and target relations. These successive runs
describe sensitivity to implementation and workload choices. Attribution to
individual planner, locking or retry mechanisms would require additional controls.

Throughput is committed target writes per wall-clock second from the worker start
barrier to the last worker finishing, including retries. Each numbered column
is the dimensionless ratio of the lock-arm rate to the SSI rate at the same
round, worker count, fanout and seed. The median summarizes six paired ratios.
Losses count strictly lower unrounded rates. Fanout counts dependency rows per
proposal. All 288 campaigns enter the comparison.

| Round | Workers | Fanout | Arm / SSI | 0 | 1 | 2 | 3 | 4 | 5 | Median | Losses / 6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 1 | 1 | Shared | 0.898 | 1.077 | 0.870 | 0.970 | 0.951 | 1.159 | 0.960 | 4 |
| v1 | 1 | 1 | Exclusive | 0.920 | 1.496 | 1.095 | 0.859 | 1.130 | 1.064 | 1.080 | 2 |
| v1 | 1 | 8 | Shared | 0.925 | 0.862 | 1.088 | 0.938 | 0.337 | 0.975 | 0.931 | 5 |
| v1 | 1 | 8 | Exclusive | 1.026 | 0.824 | 0.870 | 0.924 | 0.777 | 1.154 | 0.897 | 4 |
| v1 | 4 | 1 | Shared | 0.948 | 0.767 | 0.641 | 1.250 | 1.180 | 0.734 | 0.857 | 4 |
| v1 | 4 | 1 | Exclusive | 0.550 | 0.331 | 0.318 | 0.515 | 0.579 | 0.414 | 0.464 | 6 |
| v1 | 4 | 8 | Shared | 2.098 | 1.569 | 1.859 | 2.077 | 3.042 | 1.106 | 1.968 | 0 |
| v1 | 4 | 8 | Exclusive | 0.654 | 0.842 | 1.148 | 0.869 | 1.175 | 0.368 | 0.856 | 4 |
| v2 | 1 | 1 | Shared | 0.974 | 0.922 | 1.099 | 0.773 | 1.068 | 0.827 | 0.948 | 4 |
| v2 | 1 | 1 | Exclusive | 0.953 | 0.830 | 1.142 | 0.802 | 1.058 | 0.663 | 0.891 | 4 |
| v2 | 1 | 8 | Shared | 1.008 | 0.839 | 1.211 | 0.946 | 0.809 | 1.021 | 0.977 | 3 |
| v2 | 1 | 8 | Exclusive | 0.958 | 0.753 | 1.020 | 1.019 | 1.010 | 0.963 | 0.987 | 3 |
| v2 | 4 | 1 | Shared | 0.856 | 0.623 | 1.312 | 0.975 | 0.426 | 1.151 | 0.916 | 4 |
| v2 | 4 | 1 | Exclusive | 0.567 | 0.418 | 0.519 | 0.661 | 0.533 | 0.355 | 0.526 | 6 |
| v2 | 4 | 8 | Shared | 1.149 | 0.793 | 1.206 | 2.552 | 4.092 | 1.979 | 1.592 | 1 |
| v2 | 4 | 8 | Exclusive | 0.840 | 0.511 | 0.865 | 1.045 | 1.328 | 0.986 | 0.926 | 4 |
| v3 | 1 | 1 | Shared | 1.062 | 0.870 | 0.945 | 0.922 | 0.935 | 0.911 | 0.929 | 5 |
| v3 | 1 | 1 | Exclusive | 1.038 | 0.852 | 0.931 | 0.942 | 0.843 | 0.767 | 0.892 | 5 |
| v3 | 1 | 8 | Shared | 0.920 | 0.248 | 0.583 | 0.957 | 0.858 | 0.900 | 0.879 | 6 |
| v3 | 1 | 8 | Exclusive | 0.855 | 0.740 | 0.795 | 0.839 | 0.879 | 0.876 | 0.847 | 6 |
| v3 | 4 | 1 | Shared | 2.568 | 2.642 | 2.781 | 2.397 | 1.853 | 2.716 | 2.605 | 0 |
| v3 | 4 | 1 | Exclusive | 0.981 | 1.469 | 1.262 | 1.291 | 1.002 | 1.811 | 1.276 | 1 |
| v3 | 4 | 8 | Shared | 2.193 | 1.633 | 1.629 | 4.281 | 3.251 | 1.837 | 2.015 | 0 |
| v3 | 4 | 8 | Exclusive | 1.362 | 0.967 | 0.873 | 1.317 | 1.623 | 1.461 | 1.339 | 2 |
| v4 | 1 | 1 | Shared | 1.121 | 1.015 | 1.803 | 0.923 | 1.061 | 0.799 | 1.038 | 2 |
| v4 | 1 | 1 | Exclusive | 1.193 | 0.967 | 1.691 | 0.964 | 1.052 | 0.856 | 1.010 | 3 |
| v4 | 1 | 8 | Shared | 0.769 | 1.006 | 0.983 | 1.057 | 0.965 | 0.825 | 0.974 | 4 |
| v4 | 1 | 8 | Exclusive | 0.778 | 0.932 | 0.951 | 1.038 | 0.943 | 0.916 | 0.938 | 5 |
| v4 | 4 | 1 | Shared | 1.799 | 1.431 | 1.969 | 2.181 | 2.026 | 3.381 | 1.997 | 0 |
| v4 | 4 | 1 | Exclusive | 1.180 | 0.672 | 1.055 | 1.017 | 0.973 | 1.597 | 1.036 | 2 |
| v4 | 4 | 8 | Shared | 1.264 | 1.546 | 2.668 | 1.289 | 1.358 | 1.455 | 1.407 | 0 |
| v4 | 4 | 8 | Exclusive | 0.891 | 1.158 | 1.331 | 0.775 | 0.911 | 0.977 | 0.944 | 4 |

## Completion and readback

Each row below covers six campaigns of one arm, or 576 submitted proposals
(504 eligible and 72 stale). Commits/s is the median campaign rate. All other
outcome columns are counts summed across seeds. The four terminal outcomes
sum to 576. Retries count additional attempts after serialization failure.
Adding retries and final aborts gives the total number of serialization failures.
Missing valid counts eligible targets absent at final readback. Forbidden counts
installed targets whose proposals carried a mismatched version.

| Round | Workers | Fanout | Arm | Commits/s | Committed | Stale dep. | Stale target | Final aborts | Retries | Missing valid | Forbidden |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 1 | 1 | SSI | 295.6 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 1 | 1 | Shared | 306.0 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 1 | 1 | Exclusive | 317.7 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 1 | 8 | SSI | 319.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 1 | 8 | Shared | 300.2 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 1 | 8 | Exclusive | 306.8 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 4 | 1 | SSI | 842.0 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 4 | 1 | Shared | 711.3 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 4 | 1 | Exclusive | 379.2 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 4 | 8 | SSI | 385.9 | 212 | 72 | 0 | 292 | 0 | 292 | 0 |
| v1 | 4 | 8 | Shared | 762.1 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v1 | 4 | 8 | Exclusive | 343.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 1 | SSI | 335.7 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 1 | Shared | 299.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 1 | Exclusive | 304.4 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 8 | SSI | 328.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 8 | Shared | 310.3 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 8 | Exclusive | 310.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 4 | 1 | SSI | 787.3 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 4 | 1 | Shared | 674.1 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 4 | 1 | Exclusive | 413.4 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 4 | 8 | SSI | 492.2 | 232 | 72 | 0 | 272 | 0 | 272 | 0 |
| v2 | 4 | 8 | Shared | 771.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v2 | 4 | 8 | Exclusive | 404.2 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 1 | 1 | SSI | 329.2 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 1 | 1 | Shared | 324.8 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 1 | 1 | Exclusive | 324.6 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 1 | 8 | SSI | 309.0 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 1 | 8 | Shared | 264.5 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 1 | 8 | Exclusive | 257.8 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 4 | 1 | SSI | 334.7 | 252 | 72 | 0 | 252 | 765 | 252 | 0 |
| v3 | 4 | 1 | Shared | 841.1 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 4 | 1 | Exclusive | 435.4 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 4 | 8 | SSI | 318.6 | 243 | 72 | 0 | 261 | 767 | 261 | 0 |
| v3 | 4 | 8 | Shared | 648.3 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v3 | 4 | 8 | Exclusive | 399.8 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 1 | 1 | SSI | 310.6 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 1 | 1 | Shared | 314.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 1 | 1 | Exclusive | 329.4 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 1 | 8 | SSI | 328.7 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 1 | 8 | Shared | 303.9 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 1 | 8 | Exclusive | 305.1 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 4 | 1 | SSI | 367.3 | 270 | 72 | 0 | 234 | 753 | 234 | 0 |
| v4 | 4 | 1 | Shared | 749.2 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 4 | 1 | Exclusive | 386.0 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 4 | 8 | SSI | 440.3 | 300 | 72 | 0 | 204 | 704 | 204 | 0 |
| v4 | 4 | 8 | Shared | 620.5 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| v4 | 4 | 8 | Exclusive | 414.3 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |

Across the four rounds, SSI missed 1,515
of 8,064 eligible targets. Shared and exclusive locks missed
0 and
0, respectively.
Readback found 0 forbidden installs among
3,456 stale proposals across all arms. Each proposal is counted within its own campaign.

## Changing dependency epochs

A separately prespecified split-relation condition advanced all eight dependency
versions before each of four 24-proposal waves. Four workers then processed
21 current and three previously valid proposals in each wave. The advances
occurred between waves, so this measures invalidation across a committed version
change. The timing denominator is the sum of the four proposal intervals and
excludes version updates. Comparisons are paired within this condition.

| Round | Workers | Fanout | Arm / SSI | 0 | 1 | 2 | 3 | 4 | 5 | Median | Losses / 6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Epoch | 4 | 8 | Shared | 2.334 | 2.137 | 2.010 | 2.280 | 2.041 | 2.209 | 2.173 | 0 |
| Epoch | 4 | 8 | Exclusive | 2.272 | 2.152 | 2.056 | 2.388 | 2.050 | 2.228 | 2.190 | 0 |

| Round | Workers | Fanout | Arm | Commits/s | Committed | Stale dep. | Stale target | Final aborts | Retries | Missing valid | Forbidden |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Epoch | 4 | 8 | SSI | 739.6 | 426 | 72 | 0 | 78 | 395 | 78 | 0 |
| Epoch | 4 | 8 | Shared | 1593.7 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |
| Epoch | 4 | 8 | Exclusive | 1619.0 | 504 | 72 | 0 | 0 | 0 | 0 | 0 |

Across six campaigns per arm, readback found 78 missing eligible
targets for SSI, 0 for shared locks and 0 for
exclusive locks. The three arms together installed 0
expired proposals. This readback scores committed database state independently
of the throughput timer. Concurrent mutation during a proposal remains unmeasured.

## Reproduction

Run `python -m evaluation.venue2027.compsac.pg_development_results --check` from
the repository root to validate the campaign grid and compare this section with
the recorded measurements. The sources retain the original timings and counts.

- [v1 raw campaigns](../../proof/artifacts/compsac_pg_scope_dev_v1.json)
- [v2 raw campaigns](../../proof/artifacts/compsac_pg_scope_dev_v2.json)
- [v3 raw campaigns](../../proof/artifacts/compsac_pg_scope_dev_v3.json)
- [v4 raw campaigns](../../proof/artifacts/compsac_pg_scope_dev_v4.json)
- [Epoch raw campaigns](../../proof/artifacts/compsac_pg_epoch_dev.json)
- [Epoch condition and scoring rules](../protocols/pg_epoch_development.md)
