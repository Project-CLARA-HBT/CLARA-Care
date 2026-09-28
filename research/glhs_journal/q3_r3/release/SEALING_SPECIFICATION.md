# GLHS R3 Cryptographic Sealing & Verification Specification

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Schema Version:** `glhs-r3-sealing-spec.v1`  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Dual-SHA Provenance Baseline:**
- `system_under_test_sha`: `81f040d3e05905cc384239c5ae130f629e722d3e`
- `parent_harness_sha`: `e7a073749d8d3d434f6d47204238cc6655431f76`
- `active_branch`: `research/glhs-q2-r2-experiments`

---

## 1. Scope and Objective

This document defines the prospective cryptographic sealing, hashing, canonicalization, and provenance verification rules for all experiments (`E00` through `E14`) within the GLHS R3 research campaign.

Under the R3 novelty and reproducibility contract, **no experimental result is claim-bearing or claim-eligible** unless it complies strictly with this specification and passes cryptographic verification during clean-tree reproduction.

---

## 2. Cryptographic and Canonicalization Primitives

1. **Hash Algorithm:** Standard SHA-256 (`hashlib.sha256()` in Python 3.12, `crypto.createHash('sha256')` in Node.js 20).
   - Formatted as 64 lowercase hexadecimal characters.
2. **JSON Canonicalization:** All JSON artifacts subject to sealing must follow RFC-8785 (JSON Canonicalization Scheme - JCS):
   - Deterministic property ordering (lexicographical by UTF-16 code units).
   - Minimal whitespace (no trailing spaces, standard delimiters without extraneous formatting).
   - Consistent float/integer serialization.
   - UTF-8 encoding without BOM.

---

## 3. Per-Experiment Artifact Hierarchy

Every experiment (`E00`–`E14`) in `artifacts/glhs-r3/<run-id>/<E_ID>/` or its corresponding protocol directory must maintain the following uniform directory and file structure:

```text
<experiment_artifact_dir>/
├── protocol.json             # Complete prospective protocol declaration
├── protocol.sha256           # Standalone hex digest of protocol.json
├── freeze.json               # Timestamped registration of prospective freeze
├── environment.json          # Hardware, OS, runtime, and container baseline
├── code_manifest.json        # Git SHAs, dirty status, and submodule tree
├── backend_attestation.json  # Truthful declaration of backend characteristics
├── raw/                      # Raw byte recordings (JSONL traces, logs, pcap/csv)
├── derived/                  # Analytical aggregates, summaries, markdown tables
├── validation.json           # Automated invariant assertions and verdicts
├── checksums.sha256          # Cryptographic inventory of all files
└── seal.json                 # Terminal root signature document
```

---

## 4. Backend Attestation Contract

To eliminate ambiguity between simulated components and production storage engines, every experiment must provide `backend_attestation.json` adhering to the following schema:

```json
{
  "schema_version": "glhs-r3-backend-attestation.v1",
  "experiment_id": "E04",
  "actual_backend": "PostgreSQL 16.14",
  "endpoint": "127.0.0.1:5433",
  "version": "16.14",
  "production_path": true,
  "simulation": false,
  "network_provider": false,
  "fallback_usage": false,
  "concurrency_mechanism": "PostgreSQL Advisory Locks + Row Versioning"
}
```

### Inviolable Attestation Rules:
- **No PostgreSQL Wording for Simulations:** If in-memory simulation or mock storage is employed (e.g. testing in-memory algorithms), `simulation` MUST be `true`, `production_path` MUST be `false`, and `actual_backend` MUST explicitly state `"In-Memory Simulation"`. It is strictly forbidden to claim PostgreSQL performance or correctness from simulated runs.
- **Provider Ledger Truthfulness:** Any experiment claiming LLM provider interaction (`E11`, `E12`) must declare `network_provider: true` and supply an unredacted provider run ledger containing valid provider request/response IDs, timestamps, and model identifiers. Synthetic mocking must be marked `network_provider: false, simulation: true`.

---

## 5. Dual-SHA Provenance Invariant

Every `seal.json` and release manifest must seal the dual-SHA provenance:
1. `system_under_test_sha`: Target code commit containing the application, API, and core libraries under evaluation (`81f040d3e05905cc384239c5ae130f629e722d3e`).
2. `parent_harness_sha`: Baseline experiment harness commit establishing reproduction scripts and benchmark harnesses (`e7a073749d8d3d434f6d47204238cc6655431f76`).
3. `active_branch`: The working branch on which execution occurred (`research/glhs-q2-r2-experiments` or dedicated R3 branch).

---

## 6. Sealing Protocol & Verification Algorithm

### Phase A: Generation of `checksums.sha256`
1. Sort all files recursively within the experiment directory lexicographically by their relative path.
2. Exclude `checksums.sha256` and `seal.json`.
3. Compute SHA-256 for each file:
   ```text
   <sha256_hash>  <relative_path>
   ```
4. Write `checksums.sha256` terminated by a single newline.

### Phase B: Generation of `seal.json`
`seal.json` aggregates experiment metadata and seals the artifact inventory:
```json
{
  "schema_version": "glhs-r3-experiment-seal.v1",
  "experiment_id": "E01",
  "run_id": "GLHS-R3-E01-20260928",
  "provenance": {
    "system_under_test_sha": "81f040d3e05905cc384239c5ae130f629e722d3e",
    "parent_harness_sha": "e7a073749d8d3d434f6d47204238cc6655431f76",
    "active_branch": "research/glhs-q2-r2-experiments"
  },
  "protocol_sha256": "<hash>",
  "backend_attestation_sha256": "<hash>",
  "validation_verdict": "PASS",
  "forbidden_mutations_observed": 0,
  "claim_eligible": true,
  "artifact_inventory": {
    "protocol.json": "<hash>",
    "freeze.json": "<hash>",
    "backend_attestation.json": "<hash>",
    "validation.json": "<hash>"
  },
  "sealed_at_utc": "2026-09-28T00:00:00Z",
  "status": "SEALED"
}
```

### Phase C: Master Release Sealing
The master release manifest (`r3_manifest_template.json` -> `release_manifest.json`) aggregates all 15 experiments (`E00` through `E14`). A release is marked `"UNIFIED_RELEASE_SEALED"` only when:
- Every experiment has `claim_eligible: true` and status `"SEALED_AND_VERIFIED"`.
- Every artifact checksum is valid and verifiable.
- Dual-SHA provenance is consistent across all sub-seals.
