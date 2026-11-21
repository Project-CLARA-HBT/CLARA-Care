The earlier latency advantage disappears once each policy can dispatch a single expert call per group. On the same 9,024 Bank development rows, dense expert inference met both the original whole-batch loss ceiling (0.288085303, rounded up from frontier.csv) and its 11.392 ms latency budget at both group horizons. Its loss was 0.284356, the lowest measured. At the full offline horizon it also beat the contemporaneous whole-batch k=32 time of 0.383 ms. At the eight-batch horizon it beat the corresponding 6.553 ms. Dense timings ranged from 0.199 to 0.215 ms and 2.666 to 3.046 ms respectively across four independently timed labels executing identical endpoint code.

| Maximum batches per group | Policy at k=32 | Log loss | Full development ms |
|---:|---|---:|---:|
| 8 | Whole | 0.288662 | 6.553 |
| 8 | Packed per-batch top-k | 0.286294 | 5.725 |
| 8 | Group confidence | 0.286683 | 4.846 |
| 8 | Group learned benefit | 0.285879 | 4.433 |
| 141 | Whole | 0.288085 | 0.383 |
| 141 | Packed per-batch top-k | 0.286294 | 0.402 |
| 141 | Group confidence | 0.286417 | 0.426 |
| 141 | Group learned benefit | 0.285653 | 0.446 |

For a fixed half-budget, learned benefit gave the lowest loss at both horizons. Whole-batch selection was fastest among those four half-budget policies only with full offline visibility. Timing differences at that horizon were under 0.07 ms in this single session.

Run packed.py with bank-full.csv on CUDA and set OPENBLAS_NUM_THREADS and OMP_NUM_THREADS to 1. The split, models, order and k grid follow experiment.py. Consecutive groups contain at most eight batches (last group five) or the entire offline set. Each partial policy scores within the group, gathers the selected features, runs the expert once and scatters its probabilities. Confidence selects cheap probabilities nearest 0.5. For this fixed-width dense expert every selected row has the same nominal compute cost, so calibration ridge benefit per unit cost gives the same ranking as benefit. Wall time includes actual dispatch costs. Endpoints skip selection, with k=64 using contiguous inference. The cheap model runs for every policy. Each round shuffles all configurations within a horizon. The CSV reports medians of six synchronized full-development timings after two warmup rounds on the WSL GPU. Group formation delay, transport and preprocessing are excluded. The credit holdout stayed closed.
