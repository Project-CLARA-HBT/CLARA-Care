# Phase 9 (E09) Realistic Concurrency & Partition Benchmark Summary

**Protocol ID:** `E09-CONCURRENCY-BENCHMARK`  
**Status:** `VALIDATED` (All Invariants Passed: `True`)  
**Total Run Records:** `6870` across `1374` cell configurations

## Invariant Validation Summary

- **Entity DAG False-Stale Abort Rate on Disjoint Partitions:** `0.00%` (Target: `0.00%`) -> **PASSED**
- **Monolithic False-Stale Abort Rate on Disjoint Partitions:** `44.48%` (Baseline contention penalty)
- **Total Deadlocks Across All Runs:** `0` (Target: `0`) -> **PASSED** under canonical lock ordering
- **Minimum 5 Repetitions per Cell:** `True` -> **PASSED**

## Regime Comparison Across Evaluated Workloads

| Concurrency Regime | Avg Throughput (TPS) | Avg False-Stale Abort % | Avg True-Stale Abort % | Evaluated Cells |
| :--- | :---: | :---: | :---: | :---: |
| `entity_dag_partition_locking` | `4199.4` | `0.0%` | `13.45%` | `458` |
| `monolithic_profile_lock` | `3621.99` | `31.51%` | `0.0%` | `458` |
| `occ_backoff` | `4075.35` | `0.0%` | `13.51%` | `458` |


## 10 Multi-Workload Families Summary

| Family | Concurrency (W) | Zipf θ | Overlap | Width | Regime | Commit Rate % | False-Stale % | True-Stale % | TPS | p50 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 285.25 | 0.002 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `entity_dag_partition_locking` | 6.25% | 0.0% | 93.75% | 281.86 | 0.016 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `occ_backoff` | 6.25% | 0.0% | 93.75% | 69.53 | 9.078 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 334.13 | 0.002 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4768.09 | 0.016 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 6678.21 | 0.004 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 37.5% | 62.5% | 0.0% | 1971.99 | 0.002 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 87.5% | 0.0% | 12.5% | 4067.52 | 0.017 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 87.5% | 0.0% | 12.5% | 1016.36 | 0.005 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `monolithic_profile_lock` | 31.25% | 68.75% | 0.0% | 1517.41 | 0.002 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `entity_dag_partition_locking` | 67.5% | 0.0% | 32.5% | 2893.35 | 0.02 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `occ_backoff` | 68.75% | 0.0% | 31.25% | 781.98 | 0.006 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `monolithic_profile_lock` | 18.75% | 81.25% | 0.0% | 864.39 | 0.002 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `entity_dag_partition_locking` | 48.75% | 0.0% | 51.25% | 2122.93 | 0.018 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `occ_backoff` | 46.88% | 0.0% | 53.12% | 903.81 | 6.211 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 25.0% | 75.0% | 0.0% | 1246.53 | 0.002 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 71.25% | 0.0% | 28.75% | 3208.82 | 0.019 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 68.75% | 0.0% | 31.25% | 877.34 | 0.005 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 18.75% | 81.25% | 0.0% | 914.81 | 0.002 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 75.0% | 0.0% | 25.0% | 3402.15 | 0.017 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 75.0% | 0.0% | 25.0% | 922.2 | 0.005 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 87.5% | 12.5% | 0.0% | 4178.35 | 0.002 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4484.33 | 0.017 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 6550.06 | 0.003 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 301.31 | 0.002 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `entity_dag_partition_locking` | 56.25% | 0.0% | 43.75% | 2480.11 | 0.018 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `occ_backoff` | 56.25% | 0.0% | 43.75% | 1124.07 | 0.007 |
| `mixed` | 64 | 1.1 | 50% | 4 | `monolithic_profile_lock` | 57.81% | 42.19% | 0.0% | 2699.5 | 0.002 |
| `mixed` | 64 | 1.1 | 50% | 4 | `entity_dag_partition_locking` | 71.57% | 0.0% | 28.43% | 3005.8 | 0.02 |
| `mixed` | 64 | 1.1 | 50% | 4 | `occ_backoff` | 71.88% | 0.0% | 28.12% | 2185.13 | 0.004 |


