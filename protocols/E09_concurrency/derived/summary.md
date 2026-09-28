# Phase 9 (E09) In-Memory Concurrency Simulation Summary

> **Note:** E09 is an In-Memory Concurrency Simulation using `SimulatedPartitionCoordinator` / thread locking (NOT a production PostgreSQL benchmark).

**Protocol ID:** `E09-CONCURRENCY-BENCHMARK`  
**Status:** `VALIDATED` (All Invariants Passed: `True`)  
**Total Run Records:** `6870` across `1374` cell configurations

## Invariant Validation Summary

- **Entity DAG False-Stale Abort Rate on Disjoint Partitions:** `0.00%` (Target: `0.00%`) -> **PASSED**
- **Monolithic False-Stale Abort Rate on Disjoint Partitions:** `43.99%` (Baseline contention penalty)
- **Total Deadlocks Across All Runs:** `0` (Target: `0`) -> **PASSED** under canonical lock ordering
- **Minimum 5 Repetitions per Cell:** `True` -> **PASSED**

## Regime Comparison Across Evaluated Workloads

| Concurrency Regime | Avg Throughput (TPS) | Avg False-Stale Abort % | Avg True-Stale Abort % | Evaluated Cells |
| :--- | :---: | :---: | :---: | :---: |
| `entity_dag_partition_locking` | `4156.89` | `0.0%` | `13.34%` | `458` |
| `monolithic_profile_lock` | `3546.32` | `32.1%` | `0.0%` | `458` |
| `occ_backoff` | `4057.24` | `0.0%` | `13.43%` | `458` |


## 10 Multi-Workload Families Summary

| Family | Concurrency (W) | Zipf θ | Overlap | Width | Regime | Commit Rate % | False-Stale % | True-Stale % | TPS | p50 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 294.68 | 0.003 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `entity_dag_partition_locking` | 6.25% | 0.0% | 93.75% | 284.25 | 0.015 |
| `same_entity_contention` | 16 | 0.0 | 100% | 1 | `occ_backoff` | 6.25% | 0.0% | 93.75% | 65.52 | 9.36 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 315.27 | 0.002 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4707.85 | 0.015 |
| `disjoint_entity` | 16 | 0.0 | 0% | 1 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 8549.14 | 0.002 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 12.5% | 87.5% | 0.0% | 617.8 | 0.002 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 85.0% | 0.0% | 15.0% | 3841.46 | 0.019 |
| `partial_overlap` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 87.5% | 0.0% | 12.5% | 1229.0 | 0.005 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `monolithic_profile_lock` | 25.0% | 75.0% | 0.0% | 1166.8 | 0.002 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `entity_dag_partition_locking` | 58.75% | 0.0% | 41.25% | 2419.49 | 0.021 |
| `multi_domain` | 16 | 0.8 | 50% | 4 | `occ_backoff` | 56.25% | 0.0% | 43.75% | 671.63 | 0.006 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `monolithic_profile_lock` | 12.5% | 87.5% | 0.0% | 578.19 | 0.002 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `entity_dag_partition_locking` | 37.5% | 0.0% | 62.5% | 1656.51 | 0.017 |
| `hot_key_zipfian` | 32 | 1.4 | 75% | 2 | `occ_backoff` | 37.5% | 0.0% | 62.5% | 696.2 | 6.997 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 31.25% | 68.75% | 0.0% | 1550.58 | 0.002 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 87.5% | 0.0% | 12.5% | 4040.5 | 0.019 |
| `governance_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 87.5% | 0.0% | 12.5% | 1155.59 | 0.005 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 12.5% | 87.5% | 0.0% | 611.84 | 0.002 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 87.5% | 0.0% | 12.5% | 4069.81 | 0.018 |
| `evidence_plus_entity` | 16 | 0.8 | 25% | 2 | `occ_backoff` | 87.5% | 0.0% | 12.5% | 1138.42 | 0.005 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `monolithic_profile_lock` | 93.75% | 6.25% | 0.0% | 4406.84 | 0.002 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `entity_dag_partition_locking` | 100.0% | 0.0% | 0.0% | 4408.03 | 0.017 |
| `read_heavy` | 32 | 0.8 | 25% | 2 | `occ_backoff` | 100.0% | 0.0% | 0.0% | 6554.86 | 0.003 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `monolithic_profile_lock` | 6.25% | 93.75% | 0.0% | 306.4 | 0.002 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `entity_dag_partition_locking` | 58.75% | 0.0% | 41.25% | 2631.25 | 0.018 |
| `write_heavy` | 32 | 1.1 | 50% | 2 | `occ_backoff` | 62.5% | 0.0% | 37.5% | 1176.04 | 0.005 |
| `mixed` | 64 | 1.1 | 50% | 4 | `monolithic_profile_lock` | 45.31% | 54.69% | 0.0% | 2096.21 | 0.002 |
| `mixed` | 64 | 1.1 | 50% | 4 | `entity_dag_partition_locking` | 63.12% | 0.0% | 36.88% | 2609.59 | 0.021 |
| `mixed` | 64 | 1.1 | 50% | 4 | `occ_backoff` | 60.94% | 0.0% | 39.06% | 1740.92 | 0.007 |


