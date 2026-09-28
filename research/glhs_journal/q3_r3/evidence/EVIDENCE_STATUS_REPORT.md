# GLHS R3 Evidence Status Report: Phase 5 & Phase 6 Experiments (E01–E10)

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Curator / Role:** Agent D — Implementation & Reproducibility  
**Date:** 2026-09-29  
**Status:** ALL P0 AND PHASE 6 SYSTEMS EXPERIMENTS COMPLETE, CRYPTOGRAPHICALLY SEALED, AND REPRODUCED  
**Provenance Baseline:**
- `system_under_test_sha`: `81f040d3e05905cc384239c5ae130f629e722d3e`
- `parent_harness_sha`: `e7a073749d8d3d434f6d47204238cc6655431f76`
- `active_branch`: `research/glhs-q2-r2-experiments`

---

## 1. Executive Status Matrix

Every experiment (`E01` through `E10`) has completed raw execution, analytical derivation, automated invariant validation, cryptographic inventory hashing, and prospective sealing. All artifacts reside in tracked repository paths under `research/glhs_journal/q3_r3/evidence/`.

| Exp ID | Directory | Actual Backend | Scientific Unit | Sample Size $N$ | Primary Estimand | Secondary Estimand | Seal Status | Claim Eligible |
|---|---|---|---|---|---|---|---|---|
| **E01** | `E01_inference_consumption` | PostgreSQL 16.14 / Gateway Kernel | Frozen logical schedule | 768 | False Admission = 0.000 (Upper 95% Wilson < 0.58%) | Clean Control Admitted = 100.0% (128/128) | `SEALED` | **YES** |
| **E02** | `E02_component_ablation` | PostgreSQL 16.14 / Isolated Engine | Factorial arm schedule | 2,816 | Ablated Arm FAR = 1.000 ($p < 10^{-76}$) | Full Arm Clean Admitted = 100.0% | `SEALED` | **YES** |
| **E03** | `E03_minimal_baseline` | PostgreSQL 16.14 / Comparator Harness | Logical schedule replay | 1,408 | Decision Disagreement = 42.6% (150/352) | Token Bytes: 128B (MIN) vs 680B (GLHS) | `SEALED` | **YES** |
| **E04** | `E04_postgres_toctou` | PostgreSQL 16.14 (`127.0.0.1:5433`) | Logical adversarial schedule | 2,280 | Forbidden Commits = 0 (Upper 95% CP < 0.16%) | Clean Control Commits = 100.0% | `SEALED` | **YES** |
| **E05** | `E05_dependency_completeness` | PostgreSQL 16.14 / Dependency Validator | Mutation vector execution | 312 | Mutant Rejection = 100.0% (204/204) | False-Stale Aborts under Superset = 0 | `SEALED` | **YES** |
| **E06** | `E06_anti_downgrade` | PostgreSQL 16.14 / Lineage Gateway | Attack pattern schedule | 300 | Laundering Rejection = 100.0% (250/250) | Clean Review Chains Admitted = 50/50 | `SEALED` | **YES** |
| **E07** | `E07_canonicalization` | CPython 3.12 + Node.js 20 V8 | Canonical test vector | 45 | Byte Disagreement = 0/45 (100% concordance) | SHA-256 Digest Match = 100.0% (45/45) | `SEALED` | **YES** |
| **E08** | `E08_formal_assurance` | TLC Model Checker 2.18 (TLA+) | State-space node ($d=6$) | 69,342 | Invariant Violations = 0 (across $I_{01}$–$I_{15}$) | Reachable States: 69,342; Transitions: 378,602 | `SEALED` | **YES** |
| **E09** | `E09_concurrency` | SimulatedPartitionCoordinator / Thread Locking | Concurrent workload cell trial | 6,870 | False-Stale Abort Rate (Disjoint) = 0.0% | Deadlock Count = 0 across 10 contention families | `SEALED` | **YES** |
| **E10** | `E10_fullstack` | PostgreSQL 16.14 / FastAPI Gateway Boundary | REST operation cycle | 700 | p95 Latency < 30ms (read/reconstruct) | Write Amplification Factor WAF = 14.0 | `SEALED` | **YES** |

---

## 2. Directory Artifact Invariant Audit

Every experiment directory strictly enforces the uniform R3 artifact hierarchy:
```text
research/glhs_journal/q3_r3/evidence/<EXP_DIR>/
├── protocol.json             # Prospective protocol declaration
├── protocol.sha256           # Hex digest matching protocol.json
├── freeze.json               # Timestamped registration of prospective freeze
├── environment.json          # Hardware, runtime, and container baseline
├── code_manifest.json        # Git SHAs, branch, dirty working tree status
├── backend_attestation.json  # Truthful declaration of backend characteristics
├── raw/
│   └── runs.jsonl            # Raw byte recordings with tamper-evident Merkle hash chain
├── derived/
│   ├── summary.json          # Statistical aggregates and metrics
│   └── summary.md            # Formatted analytical markdown tables
├── validation.json           # Automated invariant assertions and verdicts
├── checksums.sha256          # Cryptographic inventory of all files
└── seal.json                 # Terminal root signature document
```

---

## 3. Cryptographic Verification & Offline Reproduction

All 10 experiments were verified offline using `research/glhs_journal/q3_r3/evidence/reproduce_all_p0.py` and dedicated Phase 6 reproduction harnesses (`reproduce_e09.py` and `reproduce_e10.py`) with external network sockets disabled:
- **Protocol SHA-256 Match Rate:** 10/10 (100.0%)
- **File Inventory Checksum Match Rate:** 100% across all tracked files
- **Merkle Hash Chain Integrity:** 100% verified across raw execution records
- **Zero Forbidden Commits / Zero Invariant Violations** observed across all test families.

Verdict: **PHASE 5 P0 CORRECTNESS AND PHASE 6 SYSTEMS EXPERIMENTAL CAMPAIGN COMPLETED & VERIFIED.**
