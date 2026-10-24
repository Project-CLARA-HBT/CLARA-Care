# LifeMap Longitudinal Security & Privacy Threat Model

**Document Status:** Sealed Security Architecture & Longitudinal Intelligence Baseline · Subagent PH12_A08  
**Repository Branch:** `phase/ph12-a08`  
**Base Commit SHA:** `36e5b95fac7e65712f0779de253d8ed18dc693d7`  
**Classification:** High-Risk Clinical Decision Support / Sensitive Health Data (PHI)  
**Review Owner:** Security + Privacy Subagent (PH12 / A08)  
**Date:** October 2026  
**Scope:** LifeMap V2 Longitudinal Intelligence, Bi-Temporal Event Query Engine, Temporal Retrieval Index Partitioning, Projection DAG Invalidation, Universal Capture Staging, Data Retention Boundaries, and Ask My LifeMap Safety Routing.

---

## 1. Executive Summary & Core Longitudinal Invariants

CLARA-Care provides longitudinal health intelligence ("LifeMap") to Vietnamese patients and their authorized care circles, structuring health events, episodes, care tasks, personal baselines, and multi-modal captures across months and years. Because longitudinal health data aggregates historical diagnoses, medications, biometric trajectories, and family observations, security and privacy failures pose catastrophic risks of profiling, unauthorized surveillance, and clinical misguidance.

The following six invariants are regression-locked across all LifeMap services:

### Invariant 1: Cross-Profile Non-Interference
> **Client-provided profile IDs (`X-CLARA-Profile-Context`) are untrusted hints. Every database query, in-memory retrieval index partition, projection cache lookup, and temporal scan MUST be server-authorized against an authenticated `ProfileScope`.**
>
> An actor cannot access, discover, or infer health records belonging to another profile. All unauthorized requests return identical, constant-time HTTP 404 responses with uniform error codes (`{"code": "profile_not_found"}`) to eliminate enumeration oracles.

### Invariant 2: Bi-Temporal Integrity & Anti-Time-Travel
> **Every longitudinal clinical fact is tracked across two distinct temporal axes: Valid Time (`occurred_at` / `effective_start` to `effective_end`) and Transaction/System Time (`recorded_at`). Event revision histories are strictly append-only.**
>
> Retroactive updates or corrections do not rewrite history; they create new revisions (`LifeMapEventRevision`) referencing prior state with cryptographically verified attribution. System time (`recorded_at`) is server-generated (UTC) and immutable, preventing audit trail spoofing or retroactive justification.

### Invariant 3: Projection DAG Invalidation Completeness
> **When an event revision is disputed, corrected, or invalidated, all downstream derived projections (personal baselines, timeline summaries, next best questions) MUST be recursively invalidated via the projection dependency graph.**
>
> No stale, revoked, or contradicted clinical state may survive in caches. Traversal bounds in `invalidate_projection_graph` guarantee cycle-free, exhaustive graph pruning before any subsequent client read is served.

### Invariant 4: Bounded In-Memory Temporal Retrieval Sandboxing
> **The `TemporalRetrievalIndex` is physically partitioned by `profile_partition`. Document lookups cannot traverse partition boundaries. Custom or neural rerankers are sandboxed: any reranker returning candidate IDs outside the pre-authorized candidate set triggers an immediate `RetrievalBoundaryError` and fails closed.**

### Invariant 5: Automated Retention Sweep & Clean Tombstoning
> **Unconfirmed capture drafts, temporary multimodal upload artifacts (audio recordings, prescription images), and abandoned sessions MUST be swept and physically deleted upon expiry (`expire_capture_drafts`). Confirmed medical truth is retained under strict 10-year statutory archiving with minimum-data audit records.**
>
> Source revocations (`LifeMapSourceRevocation`) immediately tombstone all derived records from patient timelines without data corruption.

### Invariant 6: Emergency Fast-Path & Anti-Diagnostic Gate
> **Longitudinal queries submitted to Ask My LifeMap (`route_ask_query`) MUST pass unconditional emergency detection and legal hard-guards before materializing any health data.**
>
> Queries indicating acute distress (chest pain, dyspnea, loss of consciousness) immediately return emergency escalation copy without LLM latency. Queries demanding medical diagnosis or dosage prescription are rejected with statutory disclaimers in Vietnamese and English.

---

## 2. System Architecture & Temporal Data Flow

The LifeMap longitudinal intelligence pipeline encompasses five distinct processing layers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                CLIENT INTERACTION LAYER                                │
│       Web Browser / Flutter Mobile (HttpOnly Cookie Auth + X-CLARA-Profile-Context)     │
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         │ HTTPS / JSON API
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY & AUTHORIZATION BOUNDARY                         │
│  • RBAC / CSRF Enforcement (`services/api/src/clara_api/core/`)                        │
│  • ProfileScope Resolution (`services/api/src/clara_api/lifemap/profile_scope.py`)     │
│  • Emergency Fast-Path & Intent Gate (`lifemap/intelligence.py:route_ask_query`)       │
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         │ Authorized ProfileScope
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
┌──────────────────────────────────────┐    ┌──────────────────────────────────────────┐
│     BI-TEMPORAL EVENT REPOSITORY     │    │       EPHEMERAL RETRIEVAL INDEX          │
│ • LifeMapEvent & EventRevision       │    │ • TemporalRetrievalIndex                 │
│ • Valid time: occurred_at            │    │ • Partitioned strictly by profile        │
│ • System time: recorded_at           │    │ • Sandboxed candidate scoring            │
│ • Profile-bound SQL predicates       │    │ • Zero cross-partition leakage          │
└──────────────────┬───────────────────┘    └──────────────────┬───────────────────────┘
                   │                                           │
                   ▼                                           ▼
┌──────────────────────────────────────┐    ┌──────────────────────────────────────────┐
│      PROJECTION INVALIDATION DAG     │    │       UNIVERSAL CAPTURE & RETENTION      │
│ • LifeMapProjectionDependency        │    │ • Staged drafts (LifeMapCaptureCandidate)│
│ • Recursive invalidation traversal   │    │ • Automated TTL sweep (`capture_cleanup`)│
│ • Cache eviction on dispute/amend    │    │ • Physical artifact deletion on expiry   │
└──────────────────────────────────────┘    └──────────────────────────────────────────┘
```

---

## 3. STRIDE Threat Analysis & Enforced Controls

| Threat Category | Specific Threat Description | Affected Surface / Component | Enforced Technical Control | Code Anchor & Regression Evidence |
|---|---|---|---|---|
| **Spoofing** | Adversary supplies forged `X-CLARA-Profile-Context` header to query another patient's timeline. | `lifemap_timeline`, `ask_lifemap_v2`, `ProfileScope` | Server resolves profile against authenticated user ID or active, unrevoked `FamilyAccessGrant`. Mismatches yield HTTP 404. | `profile_scope.py:86-120`<br>`test_lifemap_v2_safety_contracts.py:test_profile_context_cannot_be_used_as_an_idor_or_enumeration_oracle` |
| **Tampering** | Malicious client backdates `recorded_at` or alters prior event revisions to manipulate medical timeline. | `LifeMapEventRevision`, DB transactions | `recorded_at` is server-generated UTC timestamp. Revisions are append-only; prior revisions are never updated in place. | `models.py:1941-1965`<br>`test_lifemap_v2_safety_contracts.py:test_revision_comparison_is_profile_isolated` |
| **Tampering** | Stale or poisoned clinical state survives in projection cache after a diagnosis or medication is disputed. | Personal baselines, timeline summaries, Ask My LifeMap | `invalidate_projection_graph` traverses dependency DAG and purges all dependent projection rows on revision change. | `projection_invalidation.py:55-131`<br>`test_lifemap_projection_invalidation.py:test_invalidate_projection_graph` |
| **Repudiation** | User disputes a medical entry or revokes a clinic source; system leaves no audit trail of revocation. | Source revocation, dispute ledger, PHR audit | `LifeMapSourceRevocation` and `LifeMapDisputeAction` record actor, timestamp, and reason code with immutable audit log. | `models.py:1624-1645`<br>`lifemap.py:2404-2450`<br>`test_lifemap_v2_safety_contracts.py:test_dispute_workflow_is_profile_isolated` |
| **Information Disclosure** | Temporal query boundary leakage: query with `valid_time_from` or `episode_id` matches records outside authorized range or profile. | `GET /api/v1/lifemap/timeline`, `TemporalRetrievalIndex` | Hard SQL WHERE clauses binding `profile_id == scope.profile.id` and normalized UTC boundaries; in-memory partition isolation. | `endpoints/lifemap.py:1957-1981`<br>`temporal_index.py:82-91`<br>`test_lifemap_temporal_index.py` |
| **Information Disclosure** | Neural or statistical reranker in `TemporalRetrievalIndex` injects or returns candidate document IDs from another profile. | `TemporalRetrievalIndex.search()` | Strict candidate set validation: if `set(ordered_ids)` is not a subset of pre-filtered candidates, raises `RetrievalBoundaryError`. | `temporal_index.py:135-142`<br>`test_lifemap_temporal_index.py:test_reranker_cannot_introduce_or_duplicate_document_ids` |
| **Information Disclosure** | PII/PHI leakage in longitudinal analytics, metrics, or log aggregation. | Outbox relay, OpenTelemetry exporter, Cron sweeps | Outbox envelopes omit clinical payloads; logs record counts and anonymized entity IDs only. No drug names or symptoms logged. | `outbox_relay.py:25-45`<br>`run_retention_sweep.sh:59-61` |
| **Denial of Service** | Deep recursion or cyclic projection dependencies exhaust server memory or stack during invalidation. | `invalidate_projection_graph` | `visited` set tracks processed projection keys; queue processing breaks cycles deterministically. Batch sizes capped at 1000. | `projection_invalidation.py:75-105` |
| **Denial of Service** | Unbounded temporal query parameters trigger full-table sequential scans across millions of historical events. | `GET /api/v1/lifemap/timeline`, `revisions` | Compulsory pagination (`limit <= 500`, default 100); compound B-tree index on `(profile_id, occurred_at DESC, id DESC)`. | `endpoints/lifemap.py:1946-1947`<br>`alembic/versions/` |
| **Elevation of Privilege** | Family caregiver granted access to `vitals` attempts to query `medications` or `lifemap_ask` via temporal endpoints. | Family grants, `resolve_profile_scope` | `ProfileScope.allowed_data_classes` strictly checked. Temporal queries filter out unauthorized data classes prior to scoring. | `profile_scope.py:28-34`<br>`temporal_index.py:87`<br>`test_lifemap_v2_safety_contracts.py:test_family_grant_rejects_data_class_escalation` |
| **Elevation of Privilege** | Platform administrator uses administrative JWT to inspect user's longitudinal medical records. | RBAC, `ProfileScope` | Administrative roles confer zero implicit health-profile data access. Admin access without explicit patient grant returns 403. | `profile_scope.py:49-64`<br>`test_lifemap_v2_safety_contracts.py:test_doctor_requires_a_live_grant_and_admin_role_is_not_profile_access` |

---

## 4. LINDDUN Privacy Threat Analysis & Mitigations

| Privacy Threat Category | Threat Scenario | Technical Mitigation | Verification Anchor |
|---|---|---|---|
| **Linkability** | Longitudinal biometric trajectories (e.g. daily blood pressure, glucose curves) correlated across disparate research datasets. | Exported data scrubbed of persistent public IDs; all research exports use deterministic pseudonymization with keyed hashing. | `FHIR_PATIENT_IDENTIFICATION_AND_DEIDENTIFICATION_SPEC.md`<br>`contracts/consumer-terminology/` |
| **Identifiability** | Rare disease combinations or exact timestamps in timeline events allow re-identification in aggregate logs. | Audit logs exclude event payloads and exact timestamps in external telemetry; only coarse daily buckets recorded. | `core/telemetry.py`<br>`compliance/retention.py` |
| **Non-repudiation** | Patient disputes erroneous clinical observation entered by a clinic; deleted event persists as active fact. | Event marked `invalidated` or `disputed`; current projection excludes it; revision log retains cryptographic lineage of dispute. | `domain.py:34-40`<br>`lifemap.py:930-975` |
| **Detectability** | Timing differences between existent and non-existent profile IDs in timeline queries reveal account presence. | Constant-time password/profile resolution; uniform HTTP 404 response body and error code across all unauthorized lookups. | `profile_scope.py:100-140` |
| **Disclosure of Information** | Unconfirmed capture drafts (containing photos of prescription slips or lab slips) leak to unauthorized third parties. | Drafts stored in private object store with signed short-lived URLs; accessible only to owning profile; automated 7-day sweep. | `capture_artifacts.py:45-80`<br>`capture_cleanup.py:22-65` |
| **Unawareness** | Patient unaware that shared caregiver can view historical episodes recorded before the care relationship began. | Family grant UI requires explicit data class and date range scoping; audit log records every caregiver access. | `family.py:513-550`<br>`profile_scope.py:165-210` |
| **Non-compliance** | Abandoned multimodal drafts retained indefinitely in violation of Vietnam Decree 13/2023/ND-CP data minimization rules. | Scheduled cron execution of `expire_capture_drafts` physically unlinks storage objects and marks sessions expired. | `capture_cleanup.py:50-55`<br>`scripts/ops/run_retention_sweep.sh` |

---

## 5. Security Architecture Traceability Matrix

| Requirement / Invariant | Implementation Anchor | Test / Verification Anchor | Operational Audit Rule |
|---|---|---|---|
| **Profile Isolation** | `services/api/src/clara_api/lifemap/profile_scope.py:86` | `services/api/tests/test_lifemap_v2_safety_contracts.py:48` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_PROFILE_SCOPE_ENFORCEMENT` |
| **Temporal Query Bounds** | `services/api/src/clara_api/lifemap/temporal_index.py:82` | `services/api/tests/test_lifemap_temporal_index.py:31` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_TEMPORAL_INDEX_PARTITIONING` |
| **Reranker Sandboxing** | `services/api/src/clara_api/lifemap/temporal_index.py:135` | `services/api/tests/test_lifemap_temporal_index.py:46` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_RERANKER_CANDIDATE_SANDBOX` |
| **Projection Invalidation**| `services/api/src/clara_api/lifemap/projection_invalidation.py:55` | `services/api/tests/test_lifemap_projection_invalidation.py:20` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_PROJECTION_INVALIDATION_RECURSION` |
| **Draft Expiry Sweep** | `services/api/src/clara_api/lifemap/capture_cleanup.py:22` | `services/api/tests/test_lifemap_capture_cleanup.py:15` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_CAPTURE_DRAFT_RETENTION_EXPIRY` |
| **Statutory Retention** | `services/api/src/clara_api/compliance/retention.py:69` | `services/api/tests/test_compliance_retention.py:10` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_STATUTORY_RETENTION_BOUNDARIES` |
| **Emergency Intent Gate**| `services/api/src/clara_api/lifemap/intelligence.py:125` | `services/api/tests/test_lifemap_intelligence.py:15` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_EMERGENCY_FAST_PATH_PRESERVATION` |
| **No-PII Telemetry** | `services/api/src/clara_api/lifemap/outbox_relay.py:25` | `services/api/tests/test_lifemap_outbox_relay.py:10` | `scripts/ops/audit_longitudinal_security_regression.py:RULE_NO_PII_LONGITUDINAL_TELEMETRY` |

---

## 6. Residual Risks & Operational Directives

1. **Database Direct Access & Break-Glass Support:**  
   Direct SQL access bypasses application-level `ProfileScope` checks. Direct DB access requires dual-custody authorization, session recording, and real-time alerting. No production migrations may disable foreign keys or row tenancy constraints.
2. **Cross-Tenant Aggregate Queries:**  
   Population-level health trend analytics (e.g. seasonal epidemic monitoring) must execute against de-identified, k-anonymized warehouse replicas with `k >= 5`, never against transactional OLTP databases.
3. **Third-Party Health Device Integration:**  
   Wearable sensor feeds (e.g. continuous glucose, SpO2) must pass through the Universal Capture staging gate and undergo temporal anomaly smoothing before writing confirmed baseline revisions.
