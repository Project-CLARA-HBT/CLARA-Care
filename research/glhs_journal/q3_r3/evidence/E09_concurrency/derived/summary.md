# Phase 9 (E09) In-Memory Concurrency Simulation Summary

> **Note:** E09 is an In-Memory Concurrency Simulation using `SimulatedPartitionCoordinator` / thread locking (NOT a production PostgreSQL benchmark).

**Protocol ID:** `E09-CONCURRENCY-BENCHMARK`  
**Status:** `VALIDATED` (All Invariants Passed: `True`)  
**Total Run Records:** `6870` across `1374` cell configurations

## Invariant Validation Summary

- **Entity DAG False-Stale Abort Rate on Disjoint Partitions:** `0.00%` (Target: `0.00%`) -> **PASSED**
- **Monolithic False-Stale Abort Rate on Disjoint Partitions:** `45.56%` (Baseline contention penalty)
- **Total Deadlocks Across All Runs:** `0` (Target: `0`) -> **PASSED** under canonical lock ordering
- **Minimum 5 Repetitions per Cell:** `True` -> **PASSED**

## Regime Comparison Across Evaluated Workloads

| Concurrency Regime | Avg Throughput (TPS) | Avg False-Stale Abort % | Avg True-Stale Abort % | Evaluated Cells |
| :--- | :---: | :---: | :---: | :---: |
| `entity_dag_partition_locking` | `4034.39` | `0.0%` | `12.89%` | `458` |
| `monolithic_profile_lock` | `3449.65` | `31.89%` | `0.0%` | `458` |
| `occ_backoff` | `4038.52` | `0.0%` | `13.13%` | `458` |


## 10 Multi-Workload Families Summary

| Family | Concurrency (W) | Zipf θ | Overlap | Width | Regime | Commit Rate % | False-Stale % | True-Stale % | TPS | p50 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 288.48 | 0.002 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `entity_dag_partition_locking` | 6.25% | 0.0% | 93.75% | 285.14 | 0.016 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `occ_backoff` | 6.25% | 0.0% | 93.75% | 69.26 | 8.672 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 297.44 | 0.002 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4786.09 | 0.017 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 6814.36 | 0.004 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 18.75% | 81.25% | 0.0% | 913.24 | 0.002 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 87.5% | 0.0% | 12.5% | 4065.37 | 0.019 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 87.5% | 0.0% | 12.5% | 1088.7 | 0.005 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `monolithic_profile_lock` | 37.5% | 62.5% | 0.0% | 1671.86 | 0.002 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `entity_dag_partition_locking` | 58.75% | 0.0% | 41.25% | 2509.64 | 0.02 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `occ_backoff` | 56.25% | 0.0% | 43.75% | 630.97 | 0.008 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `monolithic_profile_lock` | 18.75% | 81.25% | 0.0% | 872.87 | 0.002 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `entity_dag_partition_locking` | 47.5% | 0.0% | 52.5% | 2060.87 | 0.018 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `occ_backoff` | 46.88% | 0.0% | 53.12% | 873.29 | 6.288 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 37.5% | 62.5% | 0.0% | 1850.61 | 0.002 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 81.25% | 0.0% | 18.75% | 3922.21 | 0.019 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 75.0% | 0.0% | 25.0% | 888.67 | 0.005 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 18.75% | 81.25% | 0.0% | 914.45 | 0.002 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 87.5% | 0.0% | 12.5% | 3994.8 | 0.02 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 87.5% | 0.0% | 12.5% | 1167.77 | 0.004 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 96.88% | 3.12% | 0.0% | 4617.47 | 0.002 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4537.43 | 0.017 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 7158.5 | 0.003 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `monolithic_profile_lock` | 9.38% | 90.62% | 0.0% | 445.93 | 0.002 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `entity_dag_partition_locking` | 56.25% | 0.0% | 43.75% | 2475.3 | 0.019 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `occ_backoff` | 56.25% | 0.0% | 43.75% | 1130.29 | 0.009 |
| `mixed` | 64 | 1.1 | 50% | 4 | `monolithic_profile_lock` | 49.69% | 50.31% | 0.0% | 2249.0 | 0.002 |
| `mixed` | 64 | 1.1 | 50% | 4 | `entity_dag_partition_locking` | 70.0% | 0.0% | 30.0% | 2829.69 | 0.022 |
| `mixed` | 64 | 1.1 | 50% | 4 | `occ_backoff` | 67.19% | 0.0% | 32.81% | 2055.04 | 0.005 |


