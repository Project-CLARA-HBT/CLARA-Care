# W8 runtime totals and derived efficiency (non-budget-normalized)

These efficiency rows are derived from the sealed runtime_stats and are explicitly NOT budget-normalized (GMT-04); W8 strategies ran with unconstrained wall-clock budgets.

| method | executions | total_ms | mean_ms | median_ms | killed | denominator | unique_kills | incremental_kills | kills_per_minute | cost_per_incremental_kill_ms |
|---|---|---|---|---|---|---|---|---|---|---|
| M0_regression | 45 | 1141775.437 | 25372.787 | 22785.265 | 16 | 45 | 0 | 16 | 0.841 | 71360.965 |
| M1_stateless_property | 225 | 979887.734 | 4355.057 | 3742.347 | 4 | 45 | 0 | 1 | 0.245 | 979887.734 |
| M2_state_machine | 225 | 2726686.056 | 12118.605 | 4494.048 | 6 | 45 | 0 | 3 | 0.132 | 908895.352 |
| M3_combined | 225 | 8913881.35 | 39617.25 | 28281.934 | 20 | 45 | 0 | 0 | 0.135 | N/A |
