# E01: Component-Wise Exact-Binding Ablation Summary Report

**Freeze ID:** `GLHS-BINDING-COMPONENT-ABLATION-20260928-01`  
**Schema Version:** `glhs-binding-component-ablation-analysis.v1`  
**Claim Eligible:** `YES`  
**Total Logical Schedules:** `352` (`256` adversarial + `96` clean controls)  
**Total Arm Executions:** `2816` / `2816`  

---

## 1. Clean Controls Admissibility (100% Target)

| Arm | Description | Accepted / Total | Acceptance Rate | 95% Wilson CI |
|---|---|---:|---:|---:|
| `B000` | None (0,0,0) | 96/96 | 100.0% | [0.962, 1.000] |
| `B100` | Snapshot Identity Only (1,0,0) | 96/96 | 100.0% | [0.962, 1.000] |
| `B010` | Content Digest Only (0,1,0) | 96/96 | 100.0% | [0.962, 1.000] |
| `B001` | Evidence Membership Only (0,0,1) | 96/96 | 100.0% | [0.962, 1.000] |
| `B110` | Identity + Digest (1,1,0) | 96/96 | 100.0% | [0.962, 1.000] |
| `B101` | Identity + Evidence (1,0,1) | 96/96 | 100.0% | [0.962, 1.000] |
| `B011` | Digest + Evidence (0,1,1) | 96/96 | 100.0% | [0.962, 1.000] |
| `B111` | Full Exact Binding (1,1,1) | 96/96 | 100.0% | [0.962, 1.000] |

## 2. Invalid Acceptance Rate by Schedule Family × Arm

| Family ID | Family Name | N | B000 | B100 | B010 | B001 | B110 | B101 | B011 | B111 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `F01` | **ID-SUB** | 32 | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| `F02` | **DIGEST-MUT** | 32 | 100.0% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| `F03` | **EVIDENCE-OUTSIDE** | 32 | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| `F04` | **MIN-SET-SWAP** | 32 | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| `F05` | **CROSS-SNAPSHOT-SAME-VERSION** | 32 | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| `F06` | **COORD-SUB** | 32 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `F07` | **LINEAGE-ROOT-SUB** | 32 | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| `F08` | **EXPIRY-CONTROL** | 32 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `F09` | **CLEAN** | 96 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## 3. Paired McNemar Discordance vs B111 (Full Exact Binding)

| Arm | Discordant Pairs (Arm Admit / B111 Reject) | Discordant Pairs (Arm Reject / B111 Admit) | McNemar Exact p-value | Significant (p < 0.001) |
|---|---:|---:|---:|---|
| `B000` | 192 | 0 | 3.19e-58 | **YES** |
| `B100` | 96 | 0 | 2.52e-29 | **YES** |
| `B010` | 160 | 0 | 1.37e-48 | **YES** |
| `B001` | 128 | 0 | 5.88e-39 | **YES** |
| `B110` | 64 | 0 | 1.08e-19 | **YES** |
| `B101` | 32 | 0 | 4.66e-10 | **YES** |
| `B011` | 96 | 0 | 2.52e-29 | **YES** |

## 4. 2^3 Factorial Logistic Regression on Invalid Acceptance

| Factor / Interaction | Coefficient (β) | Std Error | z-statistic | p-value | Odds Ratio | 95% CI (OR) |
|---|---:|---:|---:|---:|---:|---:|
| `intercept` | 1.0989 | 0.1443 | 7.61 | 2.68e-14 | 3.0008 | [2.261, 3.982] |
| `c_id` | -1.6097 | 0.1937 | -8.31 | 9.40e-17 | 0.1999 | [0.137, 0.292] |
| `c_digest` | -0.5881 | 0.1937 | -3.04 | 2.39e-03 | 0.5554 | [0.380, 0.812] |
| `c_evidence` | -1.0989 | 0.1909 | -5.75 | 8.68e-09 | 0.3333 | [0.229, 0.485] |
| `c_id:c_digest` | 0.0004 | 0.2739 | 0.00 | 9.99e-01 | 1.0004 | [0.585, 1.711] |
| `c_id:c_evidence` | -0.3362 | 0.2981 | -1.13 | 2.59e-01 | 0.7145 | [0.398, 1.281] |
| `c_digest:c_evidence` | 0.0772 | 0.2642 | 0.29 | 7.70e-01 | 1.0803 | [0.644, 1.813] |
| `c_id:c_digest:c_evidence` | -11.5375 | 45.6359 | -0.25 | 8.00e-01 | 0.0000 | [0.000, 6845674056051021628111481982681088.000] |

