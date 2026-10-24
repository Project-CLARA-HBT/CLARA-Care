# Risk Register: PH11 Subagent A02 (FHIR Patient/Observation Import)

## Overview
This risk register evaluates clinical, architectural, security, and data integrity risks associated with importing and storing external FHIR R4 Patient and Observation resources in CLARA Care.

---

## Risk Assessment Matrix

| Risk ID | Category | Description | Likelihood | Impact | Severity | Mitigation Implemented |
|:---|:---|:---|:---:|:---:|:---:|:---|
| **RSK-PH11-001** | Clinical Safety | Untrusted external clinical data could overwrite confirmed patient health truth without clinician review. | High | Critical | **CRITICAL** | Enforced invariant: all imported FHIR records are permanently tagged with `import_trust = "untrusted_external_draft"`. Ingestion enters a staging/review lane and never alters verified PHR/LifeMap records without explicit user/clinician confirmation. |
| **RSK-PH11-002** | Multi-Tenancy & Privacy | Cross-profile contamination if external FHIR patient IDs overlap between different users. | Medium | Critical | **HIGH** | Scoped all patient and observation tables by `profile_id` with composite unique constraints `(profile_id, fhir_id)`. Multi-tenant queries filter strictly on profile boundary. |
| **RSK-PH11-003** | Ingestion Denial of Service | Maliciously crafted or oversized FHIR Bundles (excessive entries, cyclic references) exhausting database memory or transaction limits. | Medium | High | **MEDIUM** | Transactional batch processing with pre-parse structure validation; `parse_bundle` isolates malformed entries without failing the batch; payload hashes enable early duplicate short-circuiting. |
| **RSK-PH11-004** | Terminology Mismatch | Inconsistent clinical terminology or unmapped observation units causing diagnostic misinterpretation. | Medium | High | **HIGH** | Extracted observations preserve both original raw coding concepts and raw resource JSON (`raw_resource_json`). Numeric quantities require valid value representations; components (e.g., BP panels) are structured separately. |
| **RSK-PH11-005** | Migration & Rollback Failure | Schema migration failure during production deployment locking database transactions or preventing rollback. | Low | Critical | **HIGH** | Migration `20260907_0069` implements fully symmetric, verified `upgrade()` and `downgrade()` methods. Verified against SQLite and PostgreSQL DDL semantics with `check_migration_downgrade.py`. |
| **RSK-PH11-006** | Concurrency & Duplicate Mutation | Concurrent imports of the same FHIR bundle resulting in duplicate records or race conditions. | Medium | Medium | **MEDIUM** | Unique constraint on `(profile_id, idempotency_key)` and deterministic SHA-256 `raw_bundle_hash` detection ensure idempotent replay of already processed import batches. |

---

## Residual Risk Evaluation
With the implemented mitigation strategies:
- All external data remains quarantined as `untrusted_external_draft`.
- Strict database-level isolation guarantees no cross-tenant or cross-profile leakage.
- Migration is 100% reversible with zero dangling foreign keys or abandoned indexes.
Residual risk is assessed as **ACCEPTABLE FOR INTEGRATION (LOW)**.
