# E06: Dependency Completeness Contract Evaluation Report

**Freeze ID:** `GLHS-DEPENDENCY-COMPLETENESS-E06-20260928-01`  
**Schema Version:** `dep-completeness-analysis.v1`  
**Claim Eligible:** `YES`  
**Total Executions:** `312`  
**Total Unsafe Commits:** `0` (Target: 0)  
**Total False-Stale Aborts:** `0` (Target: 0)  

---

## 1. Summary by Configuration Arm

| Arm | Count | Accepted | Rejected | Unsafe Commits | False-Stale Aborts | Mean Dep Count | Mean Latency (µs) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | 27 | 27 | 0 | **0** | **0** | 5.2 | 132.49 |
| `global_fallback` | 27 | 27 | 0 | **0** | **0** | 25.2 | 180.95 |
| `mutant` | 231 | 27 | 204 | **0** | **0** | 5.0 | 103.14 |
| `superset` | 27 | 27 | 0 | **0** | **0** | 6.2 | 120.17 |

## 2. Breakdown by Mutation Class (Threat Model)

| Mutation Class | Count | Accepted | Rejected | Unsafe Commits | False-Stale Aborts | Rejection Rate | Mean Latency (µs) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `M1_omit_entity` | 27 | 0 | 27 | **0** | **0** | 100.0% | 96.90 |
| `M2_add_irrelevant` | 27 | 27 | 0 | **0** | **0** | 0.0% | 113.30 |
| `M3_mutate_entity_key` | 27 | 0 | 27 | **0** | **0** | 100.0% | 96.39 |
| `M4_mutate_access_mode` | 27 | 0 | 27 | **0** | **0** | 100.0% | 100.16 |
| `M5_mutate_version` | 27 | 0 | 27 | **0** | **0** | 100.0% | 103.77 |
| `M6_write_skew` | 27 | 0 | 27 | **0** | **0** | 100.0% | 102.78 |
| `M7_unrelated_replace` | 27 | 0 | 27 | **0** | **0** | 100.0% | 108.53 |
| `M8_omit_evidence` | 15 | 0 | 15 | **0** | **0** | 100.0% | 108.37 |
| `M9_omit_governance` | 27 | 0 | 27 | **0** | **0** | 100.0% | 100.40 |
| `conservative_superset` | 27 | 27 | 0 | **0** | **0** | 0.0% | 120.17 |
| `none` | 27 | 27 | 0 | **0** | **0** | 0.0% | 132.49 |
| `profile_global_fallback` | 27 | 27 | 0 | **0** | **0** | 0.0% | 180.95 |

---
**Conclusion:** Schema-derived dependency vectors eliminate unconstrained LLM dependency specification risk with zero unsafe commits and zero false-stale aborts.
