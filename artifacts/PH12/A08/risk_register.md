# Security and Privacy Risk Register — CLARA-Care (PH12 / A08)

**Document Status:** Sealed Audit Baseline · Subagent A08  
**Repository Branch:** `phase/ph12-a08`  
**Frozen Base Commit SHA:** `36e5b95fac7e65712f0779de253d8ed18dc693d7`  
**Audit Scope Lane:** `docs/security/`, `docs/compliance/`, `scripts/ops/`, `artifacts/PH12/A08/`  
**Date:** October 2026  
**Subject:** LifeMap Longitudinal Intelligence, Bi-Temporal Event Query Isolation, Temporal Retrieval Sandboxing, Projection DAG Invalidation, and Data Retention Boundaries.

---

## 1. Executive Summary

As part of Phase PH12 (Subagent A08: Security + Privacy), an exhaustive security, privacy, and regulatory audit was conducted on CLARA-Care's LifeMap longitudinal intelligence architecture. Longitudinal health systems aggregate years of clinical observations, personal baselines, medication histories, and family interactions. Any failure in tenant/profile boundary isolation, temporal indexing, or data retention schedules can result in massive privacy breaches or life-threatening clinical decision errors.

This risk register evaluates ten critical risk vectors:
1. **Cross-Profile IDOR via Profile Context Header:** Unauthorized access to another patient's timeline via forged headers.
2. **Bi-Temporal Manipulation:** Tampering with transaction/system time (`recorded_at`) or valid time (`occurred_at`).
3. **Stale Clinical Guidance via Incomplete Projection Invalidation:** Outdated or disputed facts surviving in projection caches.
4. **Temporal Retrieval Index Candidate Escape:** Custom or neural rerankers injecting documents across profile boundaries.
5. **Zombie Draft Exposure & Storage Media Leakage:** Unconfirmed capture drafts or raw audio/photo uploads persisting past expiry.
6. **Confused Deputy & Data Class Escalation:** Caregivers attempting to view restricted health facts via Family grants.
7. **Emergency Fast-Path Latency & Illegal Diagnosis:** LLM inference latency during acute distress or providing prohibited medical prescriptions.
8. **Administrative Privilege Misuse:** Platform administrators attempting unauthorized viewing of longitudinal PHI.
9. **Statutory Retention Non-Compliance:** Violating Vietnam Decree 13/2023/ND-CP or Medical Record Law 15/2023/QH15 archiving rules.
10. **PII/PHI Telemetry Leakage:** Clinical notes or drug regimens appearing in transactional outbox events or cron logs.

All ten risk vectors are mitigated and continuously enforced by automated regression testing (`scripts/ops/audit_longitudinal_security_regression.py`).

---

## 2. Risk Matrix & Severity Definitions

| Severity | Definition | Operational Action Required |
|:---|:---|:---|
| **CRITICAL** | Direct PHI exposure, cross-profile timeline leakage, unauthorized diagnosis/prescription, or emergency suppression. | Immediate release gate block; hotfix required. |
| **HIGH** | Stale clinical state persistence, unredacted media retention past window, or privilege boundary escalation. | Mandatory architectural mitigation prior to deployment. |
| **MEDIUM** | Inconsistent temporal formatting, unbounded batch processing, or logging hygiene anomalies. | Remediate in current sprint with operational controls. |
| **LOW / INFO** | Documentation clarity, telemetry metric nomenclature, or informational notices. | Tracked in operational maintenance backlog. |

---

## 3. Comprehensive Longitudinal Risk Inventory

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status | Mitigating Architectural Control |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **SEC-LM-01** | Authorization / IDOR | Cross-Profile Timeline Access via `X-CLARA-Profile-Context` | **CRITICAL** | Medium | Severe | **Mitigated** | Server-side `resolve_profile_scope` validates profile ownership or live Family grant; 404 on failure (`profile_scope.py:86`). |
| **SEC-LM-02** | Integrity / Lineage | Bi-Temporal Timeline Tampering & System Time Forgery | **CRITICAL** | Low | Severe | **Mitigated** | Immutable append-only revisions; `recorded_at` is server UTC clock; updates create new revision rows (`models.py:1941`). |
| **SEC-LM-03** | Safety / Clinical | Stale Medical Guidance via Broken Projection Invalidation | **HIGH** | Medium | High | **Mitigated** | Recursive `invalidate_projection_graph` purges all transitive downstream projections on revision dispute (`projection_invalidation.py:55`). |
| **SEC-LM-04** | Index / Sandboxing | Reranker Candidate Escape in Temporal Retrieval Index | **CRITICAL** | Low | Critical | **Mitigated** | Fail-closed candidate set containment check raising `RetrievalBoundaryError` on foreign ID injection (`temporal_index.py:135`). |
| **SEC-LM-05** | Retention / Privacy | Zombie Drafts & Unconfirmed Raw Media Retention | **HIGH** | High | High | **Mitigated** | Scheduled `expire_capture_drafts` unlinks S3/MinIO objects via `store.delete()` and expires drafts (`capture_cleanup.py:22`). |
| **SEC-LM-06** | Access Control | Caregiver Privilege Escalation to Restricted Data Classes | **HIGH** | Medium | High | **Mitigated** | `ProfileScope.allowed_data_classes` strictly enforced; queries filter unauthorized data classes (`profile_scope.py:29`). |
| **SEC-LM-07** | Safety / Routing | Emergency Fast-Path Latency & Prohibited Medical Diagnosis | **CRITICAL** | Medium | Severe | **Mitigated** | Heuristic emergency trigger in `route_ask_query` bypasses LLM; `_FORBIDDEN_HINTS` blocks diagnosis (`intelligence.py:125`). |
| **SEC-LM-08** | RBAC / Governance | Administrator Snooping on Longitudinal Patient Records | **HIGH** | Low | High | **Mitigated** | Zero implicit health-record access for `admin` role; clinician requires live explicit grant (`profile_scope.py:49`). |
| **SEC-LM-09** | Regulatory / Compliance | Non-Compliance with Vietnam Decree 13/2023/ND-CP | **HIGH** | Medium | High | **Mitigated** | `RETENTION_POLICY` enforces 10-year archiving for confirmed records and automated 365-day query log purging (`retention.py:69`). |
| **SEC-LM-10** | Privacy / Telemetry | PHI Leakage in Outbox Envelopes and Operational Logs | **MEDIUM** | Medium | Medium | **Mitigated** | Outbox projections omit raw notes/free text; retention sweeps emit counts only without row contents (`outbox_relay.py:25`). |

---

## 4. Detailed Risk Deep Dives & Verification Anchors

### 4.1 SEC-LM-01: Cross-Profile Timeline Access via `X-CLARA-Profile-Context`
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/profile_scope.py:86-125`
  - `services/api/src/clara_api/api/v1/endpoints/lifemap.py:1952-1967`
  - `services/api/tests/test_lifemap_v2_safety_contracts.py:test_profile_context_cannot_be_used_as_an_idor_or_enumeration_oracle`
- **Threat Vector:**
  An authenticated patient (User A) specifies User B's profile ID in the `X-CLARA-Profile-Context` header when calling `GET /api/v1/lifemap/timeline`. If the endpoint trusted the header without verifying ownership or a live delegation grant, User A could observe User B's full longitudinal health history.
- **Enforced Control:**
  `resolve_profile_scope` verifies that `profile.user_id == actor.id` or that an active, unrevoked, non-expired `FamilyAccessGrant` exists for the actor on that profile with the required action (`view`) and data class (`lifemap`). If unauthorized, it returns an indistinguishable HTTP 404 (`{"code": "profile_not_found"}`), eliminating enumeration oracles.

### 4.2 SEC-LM-03: Stale Medical Guidance via Broken Projection Invalidation
- **Severity:** **HIGH**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/projection_invalidation.py:55-131`
  - `services/api/tests/test_lifemap_projection_invalidation.py:test_invalidate_projection_graph`
- **Threat Vector:**
  A patient disputes an incorrectly recorded allergy or medication course. If the projection cache (e.g. personal baseline, Ask My LifeMap context) is not invalidated recursively, subsequent clinical interactions may continue warning about a refuted allergy or failing to detect a critical contraindication.
- **Enforced Control:**
  `invalidate_projection_graph` traverses all outgoing dependencies from the mutated revision row in `LifeMapProjectionDependency`. A `visited_inputs` set prevents infinite loops on cyclic graphs. All dependent projection nodes have `invalidated_at` set to current UTC time in the same transaction.

### 4.3 SEC-LM-04: Reranker Candidate Escape in Temporal Retrieval Index
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/temporal_index.py:135-142`
  - `scripts/ops/test_audit_longitudinal_security_regression.py:test_runtime_reranker_boundary_enforcement`
- **Threat Vector:**
  Ask My LifeMap employs a semantic temporal retrieval index. If an external neural reranker or third-party ranking algorithm is plugged in, a bug or adversarial prompt injection could cause the reranker to return document IDs that were not part of the patient's authorized candidate set, exfiltrating another patient's documents.
- **Enforced Control:**
  `TemporalRetrievalIndex.search()` computes `candidate_ids = {hit.document.document_id for hit in hits}` before invoking the reranker. It checks `if not set(ordered_ids) <= candidate_ids: raise RetrievalBoundaryError("reranker_escaped_candidate_set")`. Foreign document IDs are rejected fail-closed.

### 4.4 SEC-LM-05: Zombie Draft Exposure & Unconfirmed Media Retention
- **Severity:** **HIGH**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/capture_cleanup.py:22-66`
  - `services/api/tests/test_lifemap_capture_cleanup.py:test_expire_capture_drafts_deletes_artifacts`
- **Threat Vector:**
  Patients use Universal Capture to upload prescription slips or record symptom audio. If drafts are abandoned without confirmation, the raw images/audio containing sensitive PII/PHI linger on object storage indefinitely, violating data minimization regulations.
- **Enforced Control:**
  `expire_capture_drafts` identifies sessions where `expires_at <= now` and status is `draft` or `abandoned`. For every associated artifact, it invokes `store.delete(storage_key=artifact.storage_key)` to guarantee physical deletion, marks `deleted_at`, and expires draft candidates.

### 4.5 SEC-LM-07: Emergency Fast-Path Latency & Prohibited Medical Diagnosis
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/intelligence.py:125-135`
  - `scripts/ops/test_audit_longitudinal_security_regression.py:test_runtime_route_ask_query_emergency_and_forbidden`
- **Threat Vector:**
  A patient experiencing acute life-threatening symptoms (e.g. "dau nguc du doi", "khong tho duoc", "co giat") submits an Ask My LifeMap query. If the system routes the request through an LLM reasoning pipeline, response latency could be fatal. Furthermore, if the system generates a definitive medical diagnosis or prescribes drug dosages, it violates medical device and clinical assistant regulations.
- **Enforced Control:**
  `route_ask_query` executes synchronous heuristic keyword matching preceding any health context retrieval or LLM inference. Emergency queries immediately return `SafetyRoute(intent="timeline_lookup", emergency=True)`. Prohibited diagnosis prompts return `blocked_reason="legal_guard"` with statutory disclaimers.

---

## 5. Continuous Monitoring & Automated Gate Sign-Off

The security and privacy mitigations documented in this register are locked against regression:
- **CI / Ops Gate:** `python3 scripts/ops/audit_longitudinal_security_regression.py --fail-on-high` runs automatically in production pipelines.
- **Self-Test Suite:** `pytest scripts/ops/test_audit_longitudinal_security_regression.py -v` continuously validates that simulated security boundary breaches are flagged.
- **Residual Risk Posture:** With all 10 mitigations active and regression-locked, the residual risk for LifeMap longitudinal intelligence is **LOW / ACCEPTABLE**.
