# LifeMap Longitudinal Data Retention & Privacy Assessment

**Document Status:** Sealed Compliance Baseline · Subagent PH12_A08  
**Repository Branch:** `phase/ph12-a08`  
**Base Commit SHA:** `36e5b95fac7e65712f0779de253d8ed18dc693d7`  
**Classification:** Regulatory Compliance & Privacy Impact Assessment  
**Review Owner:** Security + Privacy Subagent (PH12 / A08)  
**Date:** October 2026  
**Applicable Legal Frameworks:**  
- Vietnam Decree No. 13/2023/ND-CP on Personal Data Protection (PDPD)  
- Vietnam Law on Medical Examination and Treatment (Law No. 15/2023/QH15)  
- Vietnam Circular No. 46/2018/TT-BYT on Electronic Medical Records (EMR)  
- Regulation (EU) 2016/679 (GDPR) — Articles 5(1)(e), 6, 9, 17, 25, and 32  
- US Health Insurance Portability and Accountability Act (HIPAA) Security Rule (45 CFR § 164.312)

---

## 1. Executive Summary & Regulatory Context

CLARA-Care processes sensitive health data (personal medical history, biometric baselines, diagnostic notes, prescription courses, family caregiver observations) through the LifeMap longitudinal intelligence system. Under Vietnam Decree 13/2023/ND-CP (Article 2.4 and Article 28), health status and private medical records constitute **Sensitive Personal Data**, subject to heightened protection, explicit patient consent, strict storage limitation, and mandatory technical safeguards.

Furthermore, under the Vietnam Law on Medical Examination and Treatment (Law No. 15/2023/QH15, Article 69) and Circular 46/2018/TT-BYT, confirmed outpatient and inpatient medical records must be archived for a minimum statutory period of **10 to 20 years** to preserve clinical and legal defensibility, while temporary, unverified draft records must not be retained indefinitely.

This document establishes the verified compliance baseline for longitudinal data retention, cross-profile isolation, and privacy-preserving lifecycle operations across CLARA-Care.

---

## 2. Statutory Data Retention Schedule

The CLARA-Care data retention policy is hard-coded in `services/api/src/clara_api/compliance/retention.py` (`RETENTION_POLICY`) and mirrored across compliance documentation. The table below specifies the lifecycle treatment for all longitudinal intelligence data categories:

| Data Category | Target Entity / Table | Statutory Retention Period | Legal Basis & Rationale | Automated Disposal Action | Regulatory Reference |
|---|---|:---:|---|---|---|
| **Confirmed Timeline Events & Revisions** | `LifeMapEvent`<br>`LifeMapEventRevision` | **3,650 days (10 years)** | Medical record archiving requirement; legal defensibility | Append-only preservation; tombstone on source revocation | VN Law 15/2023/QH15 Art. 69; GDPR Art. 9(2)(h) |
| **Health Episodes & Goals** | `LifeMapEpisode`<br>`LifeMapEpisodeGoalRevision` | **3,650 days (10 years)** | Continuity of care; longitudinal clinical context | Anonymize non-clinical metadata after consent termination | VN Circular 46/2018/TT-BYT; GDPR Art. 5(1)(e) |
| **Care Tasks & Action Ledger** | `LifeMapCareTask`<br>`LifeMapTaskAction` | **1,095 days (3 years)** | Patient treatment adherence; task tracking | Archive completed tasks; purge transient scheduling items | Decree 13/2023/ND-CP Art. 16; GDPR Art. 5(1)(e) |
| **Personal Baselines & Snapshots** | `LifeMapBaselineSnapshot`<br>`LifeMapBaselineInput` | **3,650 days (10 years)** | Long-term biometric trajectory analysis | Recomputed on demand; historical snapshots immutable | VN Law 15/2023/QH15; Decree 13/2023/ND-CP Art. 28 |
| **Unconfirmed Capture Drafts** | `LifeMapCaptureSession`<br>`LifeMapCaptureCandidate` | **7 to 30 days** | Data minimization; unverified data prevention | **Physical Hard Deletion** via `expire_capture_drafts` | Decree 13/2023/ND-CP Art. 16.3; GDPR Art. 5(1)(c) |
| **Raw Multimodal Upload Artifacts** | `LifeMapCaptureArtifact`<br>(S3/MinIO objects) | **30 days max (or on draft expiry)** | Minimization of raw audio/images containing PII | **Immediate Physical Storage Deletion** via `store.delete()` | Decree 13/2023/ND-CP Art. 16; HIPAA § 164.312(a)(2)(iv) |
| **Ephemeral Projection Cache** | `LifeMapProjectionDependency`<br>(Redis / In-memory) | **Dynamic TTL (max 24 hrs)** | Performance optimization; non-canonical derived data | Automatic invalidation via `invalidate_projection_graph` | GDPR Art. 25 (Privacy by Design) |
| **In-Memory Temporal Retrieval Index** | `TemporalRetrievalIndex` | **Process Lifetime** | Ephemeral search acceleration; zero persistent PHI | Memory-only; re-indexed from canonical DB per profile | GDPR Art. 32; Decree 13/2023/ND-CP Art. 28 |
| **Ask My LifeMap Query Logs** | `QueryModel` | **365 days (1 year)** | Operational telemetry & service monitoring | **Automated Deletion** via `run_retention_sweep` | Decree 13/2023/ND-CP Art. 16; GDPR Art. 5(1)(e) |
| **Compliance & Audit Logs** | `PhrAudit`<br>`FamilyAccessLog`<br>`ComplianceEvent` | **3,650 days (10 years)** | Legal defensibility; supervisory authority reporting | **Permanent Retention** (strictly PII-free) | VN Law 15/2023/QH15; Decree 13/2023/ND-CP Art. 38 |

---

## 3. Privacy-Preserving Lifecycle Operations

### 3.1 Universal Capture Draft Expiry Sweep (`expire_capture_drafts`)
Users frequently begin capturing health records (photographing medication packaging, dictating symptoms) but abandon the process before confirmation. Retaining unverified drafts creates severe privacy liabilities:
- **Execution Mechanism:** Invoked via `services/api/src/clara_api/lifemap/capture_cleanup.py:expire_capture_drafts`.
- **Target Sessions:** Any session in `draft` or `abandoned` status where `expires_at <= current_time`.
- **Physical Artifact Removal:** Each associated `LifeMapCaptureArtifact` undergoes mandatory cloud storage object removal (`store.delete(storage_key)`), and `deleted_at` is stamped.
- **Candidate Deactivation:** `LifeMapCaptureCandidate` rows transition from `draft` to `expired`, completely blocking activation into confirmed medical truth.
- **Batch Boundary:** Bounded processing (default 100, max 1000) prevents database locks and ensures predictable execution time.

### 3.2 Dynamic Projection Invalidation (`invalidate_projection_graph`)
When a health event is corrected, disputed, or invalidated, all downstream analytical models must be updated immediately:
- **Execution Mechanism:** `services/api/src/clara_api/lifemap/projection_invalidation.py:invalidate_projection_graph`.
- **Graph Traversal:** Performs breadth-first traversal over `LifeMapProjectionDependency` rows, recursively discovering all child projections derived from the mutated revision.
- **Cycle Prevention:** A strict `visited` set bounds graph traversal, guaranteeing termination even in cyclic dependency configurations.
- **Guaranteed Consistency:** Eliminates "phantom" clinical recommendations and ensures patients never receive outdated or contradicted advice.

### 3.3 Statutory Retention Sweep (`run_retention_sweep`)
Longitudinal query logs, expired authentication tokens, and inactive PHR profiles are sanitized on a scheduled cron cadence:
- **Execution Mechanism:** Invoked via `scripts/ops/run_retention_sweep.sh` calling `clara_api.compliance.retention.run_retention_sweep`.
- **Safe Execution Gate:** Flag-gated by `COMPLIANCE_RETENTION_JOB_ENABLED`. When disabled, the runner produces an inert, non-mutating summary.
- **PII-Free Telemetry:** Outputs a single JSON string containing counts only (e.g. `{"swept": 42, "enabled": 1}`), completely safe for cron logs and external monitoring.

---

## 4. Right to Erasure, Rectification & Source Revocation

### 4.1 Bi-Temporal Integrity vs. Right to Erasure (GDPR Art. 17 / Decree 13 Art. 16)
In healthcare systems, hard deletion of confirmed clinical records violates medical record laws (VN Law 15/2023/QH15) and endangers patient safety by erasing allergy or contraindication histories. CLARA-Care resolves this tension through bi-temporal tombstoning:
1. **Unconfirmed Data (Drafts, Captures, Uploads):** Subject to complete, unrecoverable hard deletion upon request or expiration.
2. **Confirmed Clinical Facts:** Subject to clinical dispute (`POST /api/v1/lifemap/events/{event_id}/dispute`) or invalidation (`/invalidate`). The event status transitions to `invalidated`, excluding it from all standard timeline queries, Ask My LifeMap prompts, and FHIR export bundles.
3. **Cryptographic Lineage:** The immutable revision log (`LifeMapEventRevision`) retains a cryptographic record of the invalidation (actor ID, timestamp, reason), ensuring legal defensibility while honoring patient privacy.

### 4.2 Clinic / Provider Source Revocation (`LifeMapSourceRevocation`)
When a patient severs a relationship with a clinic or revokes access to an external EMR provider:
- `POST /api/v1/lifemap/v2/sources/{source_id}/revoke` registers a formal revocation record.
- All timeline events originating from that source are automatically quarantined and hidden from patient timelines.
- Projections derived from the revoked source are invalidated across the projection graph.

---

## 5. Data Protection Impact Assessment (DPIA) Scorecard

| Assessment Dimension | Inherent Risk | Mitigating Control & Architectural Safeguard | Residual Risk | Status |
|---|:---:|---|:---:|:---:|
| **Cross-Profile Data Bleed** | **HIGH** | Strict `ProfileScope` query predicate binding; constant-time 404 non-enumeration responses. | **LOW** | **PASS** |
| **Unbounded Retention of Raw Media** | **HIGH** | Automated 7-day draft expiry sweep; physical object storage deletion. | **LOW** | **PASS** |
| **Stale Medical Guidance** | **HIGH** | Recursive projection DAG invalidation on revision amendment or dispute. | **LOW** | **PASS** |
| **Unauthorized Caregiver Access** | **HIGH** | Purpose-bound `FamilyAccessGrant` with granular data class and temporal restrictions. | **LOW** | **PASS** |
| **Reranker Candidate Injection** | **MEDIUM** | Strict `RetrievalBoundaryError` fail-closed candidate set sandbox in temporal index. | **NEGLIGIBLE** | **PASS** |
| **Emergency Intent Suppression** | **CRITICAL** | Static heuristic emergency gate in `route_ask_query` preceding all LLM inference. | **LOW** | **PASS** |
| **Administrative Privilege Misuse** | **HIGH** | Zero implicit health-record access for `admin` role; clinician requires explicit grant. | **LOW** | **PASS** |

---

## 6. Verification and Audit Sign-Off

The technical controls, retention cutoffs, and isolation mechanisms detailed in this assessment are continuously audited by the automated operational regression suite (`scripts/ops/audit_longitudinal_security_regression.py`) and verified by dedicated regression test suites (`scripts/ops/test_audit_longitudinal_security_regression.py`).
