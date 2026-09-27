# GLHS Q2-R2 Paper-Code Synchronization & Architecture Reconciliation Report

**Audited Commit SHA:** `81f040d3e05905cc384239c5ae130f629e722d3e`  
**Branch:** `research/glhs-q2-r2-experiments` (derived from `origin/codex/commitloop-phase-a`)  
**Specification Reference:** `GLHS_Q2_R2_FULL_EXPERIMENT_SPEC.md`  
**Date:** 2026-09-28  

---

## 1. Five-Agent Synthesis & Consensus Matrix

All five specialized subagents completed independent audits across Architecture, Statistics, Test Infrastructure, Reproducibility, and Red-Team Adversarial Analysis.

| Dimension | Subagent A (Architecture) | Subagent B (Statistics) | Subagent C (Test Eng) | Subagent D (Reproducibility) | Subagent E (Red Team) | Consensus Resolution |
|---|---|---|---|---|---|---|
| **Exact-Binding Invariant** | Implemented in `commit_kernel.py` + `gateway.py` with 6-phase OCC | Factorial $2^3$ ablation required ($N \ge 352$ schedules) | New package `evaluation/glhs_binding_component_ablation/` designed | Sealed schema `glhs-q2-r2-freeze.v1` defined | Claim must be framed around Exact-Disclosure Invariant, not generic OCC | **Unanimous:** Implement E01 with 8 arms ($B000$–$B111$) on real PostgreSQL. |
| **Alternative Baseline** | Need minimal read-set token to test minimality | Measure decision disagreement & metadata byte overhead | Scaffolding for `MIN_READSET_TOKEN` and `HMAC_READSET_TOKEN` | Identical E01 schedule replay required | Do not claim superiority if minimal baseline enforces same safety | **Unanimous:** Implement E02 with exact schedule parity. |
| **Concurrency & TOCTOU** | 7-class total-order lock hierarchy + PostgreSQL advisory locks | Historical V2-05/09 failed due to single-label expectation; need admissible sets | New generator for $\ge 1,024$ schedules (`evaluation/glhs_toctou_r2/`) | Ephemeral PostgreSQL container (`clara-postgres`) required | Replace single-label oracle with Admissible Outcome Sets; instrument replay | **Unanimous:** Replay E05 and execute generated E04 campaign on PostgreSQL. |
| **Dependency Completeness** | Partition versions checked if declared, but omitted deps bypass kernel | Write-skew possible under omission; need $100\%$ mutant kill rate | Production contract `dependency_contract.py` + omission suite E06 | Dependency vector digest pinned in `GlhsProposalDependency` | Schema-derived required dependencies must be mandatory at kernel boundary | **Unanimous:** Implement `services/api/src/clara_api/glhs/dependency_contract.py` and E06 mutation suite. |
| **Canonicalization** | Default write profile is `clara.canonical-json.v2-rfc8785` | Manuscript still refers to legacy v1; text must be updated | Machine-readable vectors (`testdata/glhs/canonicalization/v2/`) + Node test | RFC 8785 strict canonicalization required for Merkle digests | Verify IEEE 754 negative zero, decimal precision, and UTF-16 code units | **Unanimous:** Publish E07 vectors, run cross-runtime checks, align manuscript. |
| **Formal Assurance** | 11 invariants formalized in `evaluation/formal_governance/` | Depth 5/6 BFS enumeration with 0 violations | Invariant mutation testing (`test_invariants_mutation.py`) required | Sealed run artifact linked to Git SHA | Differentiate bounded model exploration from unbounded formal proof | **Unanimous:** Publish E08 with refinement map and mutation tests. |

---

## 2. Reconciled Mechanism Map

```
                                  GLHS GOVERNANCE & OCC MECHANISM MAP
                                  
   +-----------------------------------------------------------------------------------------------+
   | 1. Governed Data & Evidence Sources                                                          |
   |    - PhrProfile / Relational Entities (partitioned by (domain, semantic_key))                 |
   |    - GovernancePolicyEpoch (Class 1-2 Advisory Lock Anchor)                                   |
   |    - UserConsent (Class 3 Advisory Lock Anchor)                                               |
   |    - Provenance & Evidence Set (Class 4 Advisory Lock Anchor)                                 |
   +-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
   +-----------------------------------------------------------------------------------------------+
   | 2. Task-Bounded Snapshot Compilation (THSS)                                                   |
   |    - Minimal Evidence Pruning via Predicate DSL                                               |
   |    - Canonical JSON v2 (RFC 8785) Digest Computation: H_D = SHA256(JCS(SnapshotPayload))      |
   |    - Persist GlhsSnapshotManifest with Manifest Digest H_M and Validity Window [t_0, t_exp]   |
   +-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
   +-----------------------------------------------------------------------------------------------+
   | 3. Model Inference Context Binding                                                           |
   |    - Server-side GlhsInferenceContextBinding (forces consumed_thss = True)                    |
   |    - Binds (Profile ID, Snapshot ID, H_D, H_M, Evidence IDs, Actor, Purpose, Task)            |
   +-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
   +-----------------------------------------------------------------------------------------------+
   | 4. Proposal Formation & Lineage Tracking                                                     |
   |    - Schema-Derived Required Dependencies (OperationDependencyContract)                       |
   |    - Compute Dependency Vector Digest: H_deps = SHA256(JCS(NormalizedDeps))                   |
   |    - Maintain Acyclic PROV DAG: reviewed_proposal_id -> root_proposal_id                       |
   |    - Invariant: Base-version-only proposals forbidden for model origins and THSS lineages     |
   +-----------------------------------------------------------------------------------------------+
                                                  |
                                                  v
   +-----------------------------------------------------------------------------------------------+
   | 5. Six-Phase Atomic OCC Commit Kernel (Linearizable Transaction Boundary)                     |
   |    - Phase 1: Idempotency & Replay Verification                                              |
   |    - Phase 2: Canonical 7-Class Total-Order Lock Acquisition (Advisory + Row Locks)          |
   |    - Phase 3: Freshness & Dependency Revalidation (State, Policy Epoch, Consent, Leases)      |
   |    - Phase 4: Domain Mutation Callback Execution                                             |
   |    - Phase 5: Compare-And-Swap (CAS) Partition Advancement & State Transition Link Formation|
   |    - Phase 6: Commit Persistence & Transactional Outbox Dispatch                             |
   +-----------------------------------------------------------------------------------------------+
```

---

## 3. Discrepancy Resolution & Action Plan

1. **Canonicalization Profile Discrepancy:**
   - *Status:* Resolved in favor of Code (`clara.canonical-json.v2-rfc8785`).
   - *Action:* Manuscript Methods section will be updated to explicitly state RFC 8785 compliance; test vectors generated in E07.
2. **Dependency Completeness Assumption:**
   - *Status:* Resolved. Production contract `services/api/src/clara_api/glhs/dependency_contract.py` will be created to formally derive required dependencies from clinical operation schemas.
3. **TOCTOU Oracle Over-Specification:**
   - *Status:* Resolved. R2 TOCTOU executor will evaluate concurrency races against formal Admissible Outcome Sets rather than brittle single-string labels.
4. **Historical Evidence Immutability:**
   - *Status:* Resolved. All historical artifacts in `research/glhs_journal/` remain locked and immutable. All R2 artifacts will be written to `research/glhs_journal/q2_r2/` and `artifacts/glhs-q2-r2/`.

---

## 4. Phase 0 Gate Verification

- [x] Audited codex/commitloop-phase-a at `81f040d3e05905cc384239c5ae130f629e722d3e`.
- [x] Pinned baseline commit verified against clean branch `research/glhs-q2-r2-experiments`.
- [x] Reconciled all 7 core governance dimensions.
- [x] Generated `R2_IMPLEMENTATION_INVENTORY.json`, `R2_CLAIM_CODE_TRACE.csv`, and `R2_BLOCKER_LEDGER.json`.
- [x] Zero unresolved P0 code/manuscript semantic blockers.

**Phase 0 Gate: PASSED.** Ready to proceed with Phase 1 implementation.
