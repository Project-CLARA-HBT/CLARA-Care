# Phase 9 (E09) In-Memory Concurrency Simulation Summary

> **Note:** E09 is an In-Memory Concurrency Simulation using `SimulatedPartitionCoordinator` / thread locking (NOT a production PostgreSQL benchmark).

**Protocol ID:** `E09-CONCURRENCY-BENCHMARK`  
**Status:** `VALIDATED` (All Invariants Passed: `True`)  
**Total Run Records:** `6870` across `1374` cell configurations

## Invariant Validation Summary

- **Entity DAG False-Stale Abort Rate on Disjoint Partitions:** `0.00%` (Target: `0.00%`) -> **PASSED**
- **Monolithic False-Stale Abort Rate on Disjoint Partitions:** `45.65%` (Baseline contention penalty)
- **Total Deadlocks Across All Runs:** `0` (Target: `0`) -> **PASSED** under canonical lock ordering
- **Minimum 5 Repetitions per Cell:** `True` -> **PASSED**

## Regime Comparison Across Evaluated Workloads

| Concurrency Regime | Avg Throughput (TPS) | Avg False-Stale Abort % | Avg True-Stale Abort % | Evaluated Cells |
| :--- | :---: | :---: | :---: | :---: |
| `entity_dag_partition_locking` | `4236.73` | `0.0%` | `13.38%` | `458` |
| `monolithic_profile_lock` | `3597.57` | `32.53%` | `0.0%` | `458` |
| `occ_backoff` | `4129.87` | `0.0%` | `13.75%` | `458` |


## 10 Multi-Workload Families Summary

| Family | Concurrency (W) | Zipf θ | Overlap | Width | Regime | Commit Rate % | False-Stale % | True-Stale % | TPS | p50 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 290.17 | 0.002 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `entity_dag_partition_locking` | 6.25% | 0.0% | 93.75% | 288.7 | 0.016 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `occ_backoff` | 6.25% | 0.0% | 93.75% | 68.24 | 9.334 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 312.29 | 0.002 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4673.72 | 0.017 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 6795.49 | 0.004 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 25.0% | 75.0% | 0.0% | 1266.5 | 0.002 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 93.75% | 0.0% | 6.25% | 4322.04 | 0.019 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 93.75% | 0.0% | 6.25% | 1313.65 | 0.004 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `monolithic_profile_lock` | 50.0% | 50.0% | 0.0% | 2226.6 | 0.002 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `entity_dag_partition_locking` | 73.75% | 0.0% | 26.25% | 3153.44 | 0.021 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `occ_backoff` | 68.75% | 0.0% | 31.25% | 878.26 | 0.006 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `monolithic_profile_lock` | 15.62% | 84.38% | 0.0% | 742.08 | 0.002 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `entity_dag_partition_locking` | 40.62% | 0.0% | 59.38% | 1864.52 | 0.018 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `occ_backoff` | 40.62% | 0.0% | 59.38% | 779.32 | 7.033 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 31.25% | 68.75% | 0.0% | 1530.35 | 0.002 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4375.08 | 0.019 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 93.75% | 0.0% | 6.25% | 1344.76 | 0.004 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 25.0% | 75.0% | 0.0% | 1267.55 | 0.002 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 81.25% | 0.0% | 18.75% | 3652.76 | 0.018 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 81.25% | 0.0% | 18.75% | 1025.45 | 0.005 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 100.0% | 0.0% | 0.0% | 4779.87 | 0.002 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4472.42 | 0.017 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 6745.88 | 0.003 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `monolithic_profile_lock` | 12.5% | 87.5% | 0.0% | 624.38 | 0.002 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `entity_dag_partition_locking` | 53.12% | 0.0% | 46.88% | 2344.25 | 0.018 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `occ_backoff` | 53.12% | 0.0% | 46.88% | 1016.61 | 0.011 |
| `mixed` | 64 | 1.1 | 50% | 4 | `monolithic_profile_lock` | 53.43% | 46.57% | 0.0% | 2501.17 | 0.002 |
| `mixed` | 64 | 1.1 | 50% | 4 | `entity_dag_partition_locking` | 71.57% | 0.0% | 28.43% | 3031.61 | 0.02 |
| `mixed` | 64 | 1.1 | 50% | 4 | `occ_backoff` | 67.19% | 0.0% | 32.81% | 1962.61 | 0.004 |


