# GLHS R3 Protocols Repository

This directory contains prospective protocol specifications, cryptographic hash freezes (`protocol.sha256`), and the master protocol registry (`protocol_registry.json`) for experiments E00 through E14.

## Protocol Directory Structure
- `E00_code_sync/` — Phase 0: Literature/Claim Freeze, Novelty Contract & Code Synchronization
- `E01_inference_consumption/` — Phase 1: Inference Consumption Integrity & Continuous Attestation
- `E02_component_ablation/` — Phase 5: Binding Component Factorial Ablation (2^4)
- `E03_minimal_baseline/` — Phase 5: Minimal Token / Capability Comparator Baseline
- `E04_postgres_toctou/` — Phase 5: Generated PostgreSQL TOCTOU Adversarial Schedule Campaign
- `E05_dependency_completeness/` — Phase 3: Dependency Completeness & Mutation Analysis
- `E06_anti_downgrade/` — Phase 2: Anti-Downgrade & Lineage Anti-Laundering Statistical Evaluation
- `E07_canonicalization/` — Phase 5: Multi-Runtime Canonicalization Conformance & Verification
- `E08_formal_assurance/` — Phase 5: Sealed Bounded Formal Assurance (TLA+ / Model Checking)
- `E09_concurrency/` — Phase 6: Real PostgreSQL Concurrency & Contention Analysis
- `E10_fullstack/` — Phase 6: HTTP / PostgreSQL Full-Stack Performance Characterization
- `E11_model_replication/` — Phase 7: Two-Model Large Context Utility & Replication
- `E12_malformed_sensitivity/` — Phase 7: Malformed-Output Sensitivity & Error Taxonomy Analysis
- `E13_external_validation/` — Phase 8: Synthetic Source-Derived Task Suite (derived from eICU/Synthea/MIMIC/Diabetes schemas)
- `E14_reproducibility/` — Phase 9: Independent Reproduction Audit & Clean Checkout Verification

## Master Manifest
- `protocol_registry.json` — Master RFC 8785 canonical registry manifest indexing all 15 protocol definitions and their cryptographic digests.

Each protocol subdirectory contains `protocol.json` and its corresponding standalone `protocol.sha256` frozen prior to trial execution.
