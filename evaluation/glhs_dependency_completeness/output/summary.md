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
| `baseline` | 27 | 27 | 0 | **0** | **0** | 5.2 | 112.75 |
| `global_fallback` | 27 | 27 | 0 | **0** | **0** | 25.2 | 155.68 |
| `mutant` | 231 | 27 | 204 | **0** | **0** | 5.0 | 94.66 |
| `superset` | 27 | 27 | 0 | **0** | **0** | 6.2 | 100.38 |

## 2. Breakdown by Mutation Class (Threat Model)

| Mutation Class | Count | Accepted | Rejected | Unsafe Commits | False-Stale Aborts | Rejection Rate | Mean Latency (µs) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `M1_omit_entity` | 27 | 0 | 27 | **0** | **0** | 100.0% | 97.02 |
| `M2_add_irrelevant` | 27 | 27 | 0 | **0** | **0** | 0.0% | 103.39 |
| `M3_mutate_entity_key` | 27 | 0 | 27 | **0** | **0** | 100.0% | 89.08 |
| `M4_mutate_access_mode` | 27 | 0 | 27 | **0** | **0** | 100.0% | 91.34 |
| `M5_mutate_version` | 27 | 0 | 27 | **0** | **0** | 100.0% | 95.84 |
| `M6_write_skew` | 27 | 0 | 27 | **0** | **0** | 100.0% | 92.58 |
| `M7_unrelated_replace` | 27 | 0 | 27 | **0** | **0** | 100.0% | 90.16 |
| `M8_omit_evidence` | 15 | 0 | 15 | **0** | **0** | 100.0% | 94.67 |
| `M9_omit_governance` | 27 | 0 | 27 | **0** | **0** | 100.0% | 97.86 |
| `conservative_superset` | 27 | 27 | 0 | **0** | **0** | 0.0% | 100.38 |
| `none` | 27 | 27 | 0 | **0** | **0** | 0.0% | 112.75 |
| `profile_global_fallback` | 27 | 27 | 0 | **0** | **0** | 0.0% | 155.68 |

---
**Conclusion:** Schema-derived dependency vectors eliminate unconstrained LLM dependency specification risk with zero unsafe commits and zero false-stale aborts.
