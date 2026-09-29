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
| `baseline` | 27 | 27 | 0 | **0** | **0** | 5.2 | 33196.67 |
| `global_fallback` | 27 | 27 | 0 | **0** | **0** | 25.2 | 36083.05 |
| `mutant` | 231 | 27 | 204 | **0** | **0** | 0.7 | 16820.56 |
| `superset` | 27 | 27 | 0 | **0** | **0** | 6.2 | 26940.49 |

## 2. Breakdown by Mutation Class (Threat Model)

| Mutation Class | Count | Accepted | Rejected | Unsafe Commits | False-Stale Aborts | Rejection Rate | Mean Latency (µs) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `M1_omit_entity` | 27 | 0 | 27 | **0** | **0** | 100.0% | 14485.58 |
| `M2_add_irrelevant` | 27 | 27 | 0 | **0** | **0** | 0.0% | 27395.70 |
| `M3_mutate_entity_key` | 27 | 0 | 27 | **0** | **0** | 100.0% | 16202.62 |
| `M4_mutate_access_mode` | 27 | 0 | 27 | **0** | **0** | 100.0% | 17114.04 |
| `M5_mutate_version` | 27 | 0 | 27 | **0** | **0** | 100.0% | 15063.71 |
| `M6_write_skew` | 27 | 0 | 27 | **0** | **0** | 100.0% | 14486.25 |
| `M7_unrelated_replace` | 27 | 0 | 27 | **0** | **0** | 100.0% | 15328.30 |
| `M8_omit_evidence` | 15 | 0 | 15 | **0** | **0** | 100.0% | 15501.45 |
| `M9_omit_governance` | 27 | 0 | 27 | **0** | **0** | 100.0% | 15221.16 |
| `conservative_superset` | 27 | 27 | 0 | **0** | **0** | 0.0% | 26940.49 |
| `none` | 27 | 27 | 0 | **0** | **0** | 0.0% | 33196.67 |
| `profile_global_fallback` | 27 | 27 | 0 | **0** | **0** | 0.0% | 36083.05 |

---
**Conclusion:** Schema-derived dependency vectors eliminate unconstrained LLM dependency specification risk with zero unsafe commits and zero false-stale aborts.
