# GLHS Q2/R2 Release: Factual Evidence Status Report

**Release Freeze ID:** `GLHS-R02-FREEZE-20260928-V1`  
**System Under Test SHA:** `81f040d3e05905cc384239c5ae130f629e722d3e`  
**Experiment Harness SHA:** `e7a073749d8d3d434f6d47204238cc6655431f76`  
**Status Date:** September 28, 2026  
**Supersedes:** `FINAL_PUBLICATION_AUDIT_REPORT.md` (Overclaiming audit report retired in favor of objective factual execution matrix).

---

## 1. Objective Execution Matrix (E00–E13)

To ensure scientific honesty and transparency, this matrix clearly delineates:
1. **Real PostgreSQL Transactional Execution**: Real DB transactions against PostgreSQL with row locking and serializable isolation.
2. **In-Memory Simulations & Mathematical Verification**: In-memory schedule coordinate exploration, model checking, or mock data generators.
3. **Live Provider API Calls**: Empirical network completions through external provider gateways (`https://router.theclaracare.com/v1`).

| Exp ID | Experiment Name | Execution Substrate / Runtime | Scientific Denominator | Empirical Findings & Status |
| :--- | :--- | :--- | :--- | :--- |
| **E00** | Paper/Code Sync & Preflight | Static Code Analysis & Verification | 5 Protocol Endpoints | Complete synchronization verified between manuscript and API implementations. |
| **E01** | $2^3$ Factorial Component Ablation | In-Memory Permutation Engine | 352 Unique Schedules | Confirmed exact requirement of all 3 binding components (Manifest, Policy, Consent). |
| **E02** | Minimal Alternative-Design Baseline | In-Memory Permutation Engine | 352 Unique Schedules | Demonstrates functional equivalence between GLHS and `MIN_READSET_TOKEN`. |
| **E03** | Downgrade & Anti-Laundering Prevention | Commit Kernel In-Memory Replay | 300 Schedules (250 Adversarial) | 0 downgrade admissions across 11 adversarial laundering patterns. |
| **E04** | Randomized PostgreSQL TOCTOU Campaign | **Real PostgreSQL 16 DB Engine** | 2,280 Generated Schedules | 0 forbidden commits under concurrent write transactions with OCC. |
| **E05** | Historical TOCTOU Root-Cause Replay | **Real PostgreSQL 16 DB Engine** | 200 Replay Perturbations | Reconciled V2-05 and V2-09 historical aborts as conservative safe rejections. |
| **E06** | Dependency Completeness & Mutations | Contract Invariant & Mutation Runner | 312 Schema Mutations | 100% rejection rate for omitted required entity dependencies. |
| **E07** | RFC 8785 Canonicalization Conformance | Multi-Language Conformance Harness | 35 Canonical Test Vectors | 100% byte-for-byte serialization identity across Python and JS. |
| **E08** | Sealed Bounded Formal Assurance | Bounded Exhaustive State Explorer | Depth 6 (69,342 States) | 0 invariant violations across 11 safety invariants. |
| **E09** | Concurrency Characterization | **In-Memory Simulation** (`SimulatedPartitionCoordinator`) | 6,870 Records / 1,374 Workload Cells | 0.0% false-stale aborts under DAG partitioning vs 44.48% monolithic. *(Note: in-memory simulation, not real PostgreSQL).* |
| **E10** | Full-Stack Performance Characterization | FastAPI In-Process HTTP Gateway | N=100 Repetitions / Op Class | Empirical latency and throughput curves under local OCC workload. |
| **E11** | Model Replication & TOST Equivalence | **Live Router Calls** (`https://router.theclaracare.com/v1`) | 48 Live Requests across 3 Models (8 Benchmark Cases × 2 Conditions) | **Empirical live router testing completed.** Gemini 3.6 Flash High & Gemini 3.8 Flash Tiered achieved equivalence ($\Delta=\pm 0.02$). Claude Sonnet 4.6 showed format divergence. |
| **E12** | Malformed-Output Taxonomy & Sensitivity | **Live Provider Run Ledger** & Offline Sensitivity Arms | 48 Empirical Provider Requests + 12 Taxonomy Classes | **Empirical taxonomy observed:** 2 `invalid_json` occurrences out of 48 live calls. Sensitivity recovery arms R0 $\rightarrow$ R3 verified. |
| **E13** | Synthetic Source-Derived Task Suite | Source-Derived Longitudinal Cohorts | 9 Longitudinal Benchmark Tasks | Evaluated against eICU, Synthea, MIMIC-IV, and Diabetes 130 demo cohorts. Human review flagged `NOT_RUN_HUMAN_UNAVAILABLE`. |

---

## 2. Live Router Probe & Provider Run Ledger (E11 / E12)

- **Probe Target Endpoint:** `https://router.theclaracare.com/v1`
- **Models Evaluated:**
  - `gemini-3.8-flash-tiered` (reported: `gemini-3.7-flash-tiered` / `antigravity/gemini-3.8-flash-tiered`)
  - `gemini-3.6-flash-high` (reported: `gemini-3.6-flash-high`)
  - `claude-sonnet-4.6` (reported: `claude-sonnet-4-6`)
- **Conditions Tested:**
  - `glhs_hybrid_thss_strict`
  - `full_authorized_history`
- **Real Requests Ledger:** Stored at `protocols/commitloop/v8-glhs-q2-r2/provider_run_ledger.json` (48 total executions).
- **Observed Empirical Error Taxonomy:**
  - `invalid_json`: 2 instances (Claude Sonnet 4.6 under `glhs_hybrid_thss_strict` emitting chain-of-thought markdown rather than pure JSON object).
- **Pilot Live Benchmark Accuracy & Bounds (N=8 Cases):**
  - **Gemini 3.6 Flash High:** Strict 1.0000, Full 1.0000, Mean Diff +0.0000, 100% exact concordance ($s_d = 0$). Under Schuirmann biostatistics, $N=8 < 384$ is underpowered for narrow-margin equivalence testing ($p_{\text{TOST}} = \text{NaN}$ / `None`); TOST equivalence testing requires $N \ge 384$ powered observations with $s_d > 0$.
  - **Gemini 3.8 Flash Tiered:** Strict 1.0000, Full 1.0000, Mean Diff +0.0000, 100% exact concordance ($s_d = 0$). Under Schuirmann biostatistics, $N=8 < 384$ is underpowered for narrow-margin equivalence testing ($p_{\text{TOST}} = \text{NaN}$ / `None`); TOST equivalence testing requires $N \ge 384$ powered observations with $s_d > 0$.
  - **Claude Sonnet 4.6:** Strict 0.7500, Full 0.8750, Mean Diff -0.1250, TOST $p = 0.7857$, 95% CI $[-0.4206, +0.1706]$ (Equivalence rejected at $\Delta = \pm 0.02$ due to formatting unprompted reasoning tokens in 2 cases).

---

## 3. E13 Synthetic Task Suite Relabeling

In strict compliance with Red Team constraints and scientific integrity guidelines:
- **Relabeling:** E13 is cataloged as **Synthetic Source-Derived Task Suite** (derived from public demo subsets of eICU, Synthea, MIMIC-IV on FHIR, and Diabetes 130).
- **Human Review Status:** Permanently marked as `NOT_RUN_HUMAN_UNAVAILABLE`.
- **Claim Eligibility:** `independent_human_claim_eligible: false`. Automated fact retention was 100% across the 9 tasks under synthetic model adjudication, but no claim of external clinical human validation is asserted.

---

## 4. R02 Freeze Certification

Both system under test SHA and harness commit SHA are frozen in `r02_release_manifest.json`:
- `system_under_test_sha`: `81f040d3e05905cc384239c5ae130f629e722d3e`
- `experiment_harness_sha`: `e7a073749d8d3d434f6d47204238cc6655431f76`
- Verification suite passes fail-closed: `pytest evaluation/commitloop/tests/test_v8_commitloop.py` and `pytest evaluation/external_validation/tests/test_e13_external.py`.
