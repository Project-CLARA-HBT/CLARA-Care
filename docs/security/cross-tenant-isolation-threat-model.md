# Cross-Tenant Isolation & Multi-Tenant Threat Model

**Status:** Implemented Security Baseline & Threat Model  
**Review Owner:** Security + Privacy (Subagent PH04_A08)  
**Date:** 2026-10-21  
**Classification:** Restricted / High-Risk Clinical System Architecture  
**Scope:** Multi-Tenant Organizations, Workspaces, Clinical Workbenches, GLHS Commit Kernels, and PHR Profile Scopes  

---

## 1. Executive Summary & Core Invariant

CLARA-Care is designed as a multi-tenant clinical decision-support and personal health architecture serving healthcare organizations, clinical practices, research institutes, and individual patients across Vietnam.

### Core Security Invariant: Zero Cross-Tenant Data Leakage
> **Tenant A cannot view, query, or mutate Tenant B records, even if the authenticated actor possesses the `admin` role within Tenant A.**

An administrative role within one organization or tenant boundary is strictly local to that tenant. It confers zero authority, visibility, or query capability over data, users, health profiles, or transactional ledgers belonging to any other tenant.

---

## 2. Assets and Trust Boundaries

| Asset Class | Description & Confidentiality Level | Storage / Persistence | Isolation Mechanism |
|---|---|---|---|
| **Patient Health Records (PHR / LifeMap)** | Diagnoses, medications, allergies, clinical observations, genetic notes (Sensitive Personal Health Data - PDPD Art. 2(4)). | PostgreSQL `phr_profiles`, `lifemap_*` tables | `ProfileScope` resolution; mandatory `profile_id` & `user_id` query constraints; opaque public IDs. |
| **Workspace Artifacts** | Folders, channels, conversations, notes, shares. | PostgreSQL `workspace_*`, `sessions` tables | Mandatory `user_id` & `tenant_id` predicate binding in `_get_owned_*` helpers. |
| **Clinical Workbench Cases & Runs** | Oncology reviews, diagnostic transcripts, clinical workflow runs, patient rosters. | PostgreSQL `clinical_cases`, `clinical_workflow_runs`, `council_cases` | Explicit `owner_user_id` & organization scope verification; isolated patient rosters. |
| **Research Knowledge Sources** | Proprietary clinical trial datasets, uploaded research documents, custom RAG indexes. | PostgreSQL `knowledge_sources`, `knowledge_documents` | Scoped via `owner_user_id` and tenant organization binding. |
| **GLHS Commit Kernel Transitions** | Tamper-evident transition ledgers, idempotency keys, governance state versions. | PostgreSQL `glhs_applied_transitions`, advisory lock manager | Explicit `tenant_id` column; composite idempotency key namespace: `idempotency:{tenant_id}:{operation_kind}:{key}`. |
| **Session & Auth State** | JWT credentials, refresh rotation lineages, logout denylists, CSRF tokens. | Redis `security_redis_key_prefix`, PostgreSQL `users`, `auth_tokens` | Opaque SHA-256 digested tokens; Redis namespace segregation; cookie HttpOnly boundaries. |

---

## 3. Threat Vectors & Defense-in-Depth Matrix

| Threat Vector ID | Threat Vector Description | Attacker Persona | Target Surface | Enforced Architectural Control | Residual Risk & Verification Anchor |
|---|---|---|---|---|---|
| **THR-TEN-01** | **Horizontal IDOR across Tenants** | Authenticated User / Clinician in Tenant A | `/workspace/folders/{id}`, `/workspace/channels/{id}`, `/clinical-workbench/cases/{id}`, `/council/cases/{id}` | Object-level lookup helpers (`_get_owned_folder`, `_get_owned_case`, etc.) enforce strict ownership predicate (`WHERE id = :id AND user_id = :user_id`). Requests for foreign tenant IDs return **HTTP 404 Not Found** (fail-closed, non-enumerating). | Verified: `research/security_audit/test_security_negative_vectors.py:396-518`. |
| **THR-TEN-02** | **Tenant-Admin Vertical Privilege Escalation** | Organization Admin in Tenant A attempting to access Tenant B health records or workspace data | All authenticated endpoints, `resolve_profile_scope`, `require_roles` | **Admin role is not a health-data capability.** `ProfileScope` explicitly rejects admin access without an audited break-glass flow (`policy.administrative -> 404 scope_forbidden`). Role checks (`require_roles`) only open route gates within the caller's authorized tenant context. | Verified: `services/api/tests/test_rbac_profile_scope_idor.py:103-113`. |
| **THR-TEN-03** | **Identifier Enumeration Oracle** | Malicious actor probing object IDs to discover valid records in other tenants | Any entity lookup route | Unknown objects, foreign-tenant objects, and unauthorized objects return identical **HTTP 404** status codes and generic error messages (`Folder không tồn tại`, `Case không tồn tại`, `Profile not found`). No 403 or existence disclosures are emitted. | Enforced in all `_get_owned_*` functions; verified in regression suite. |
| **THR-TEN-04** | **GLHS Idempotency Collision & Transition Replay** | Actor in Tenant B reusing an idempotency key previously committed by Tenant A | GLHS commit kernel (`apply_transition`, `COMMIT_PROPOSAL`) | Advisory lock keys and database idempotency checks explicitly partition by tenant: `idempotency:{tenant_id}:{operation_kind}:{idempotency_key}`. Transition lookup enforces `GlhsAppliedTransition.tenant_id == tenant_id`. | Verified: `services/api/src/clara_api/glhs/commit_kernel.py:531, 552`. |
| **THR-TEN-05** | **Cross-Tenant Clinical Patient Roster Spillover** | Clinician in Hospital A viewing patient roster containing patients from Hospital B | `/clinical-workbench/patients` | Patient roster queries must enforce organization/care-team filtering (`PhrProfile` linked to organization membership). Masked display labels (`BN-XXXXXXXX`) prevent PII disclosure even within authorized views. | Tracked finding `ROSTER-TEN-01` in operational audit. |
| **THR-TEN-06** | **Cross-Tenant Cache Poisoning & Namespace Bleed** | Actor triggering cache generation that collides with or leaks to another tenant | Redis cache, SearXNG search cache, RAG embedding cache | Cache keys for tenant-sensitive data MUST include `{tenant_id}` or `{profile_id}` prefix. Shared public caches (e.g., standard DrugBank drug dictionary) are strictly immutable and contain zero patient or tenant data. | Invariant verified in `docs/security/privacy-checklist.md`. |
| **THR-TEN-07** | **Background Job & Transactional Outbox Bleed** | Background daemon processing outbox events for multiple tenants | Outbox workers, async task runners | Outbox event envelopes (`LifeMapOutboxEvent`) carry internal profile and tenant bindings. Workers instantiate scoped execution contexts and never broadcast cross-tenant payloads. | Verified: `LifeMapOutboxEvent` architecture. |

---

## 4. Multi-Tenant Authorization Rules

### 4.1 Strict Hierarchy of Scopes
```
Global / Platform Admin (Break-Glass Only, Time-Bounded, Audited)
  └── Organization / Tenant A
        ├── Org Admin A (Can manage Tenant A users, configs; CANNOT read PHR without consent)
        ├── Clinician A (Can manage assigned patients in Tenant A)
        └── Patient A (Can access own PHR; can grant Family Access)
  └── Organization / Tenant B (COMPLETELY ISOLATED)
        ├── Org Admin B
        ├── Clinician B
        └── Patient B
```

### 4.2 Non-Enumeration Standard (OWASP API Security Top 10 - API1:2023)
To prevent cross-tenant enumeration of UUIDs, integer IDs, or slugs:
1. **Never return HTTP 403 Forbidden for missing vs. foreign objects:** An unauthorized request for an existing object in Tenant B MUST return the exact same HTTP 404 response as a request for a non-existent object ID.
2. **Deterministic error payloads:** Error responses must use standardized, localized Vietnamese messages without reflecting requested entity IDs or owner metadata.

### 4.3 Break-Glass Support Protocol
1. Global administrators do NOT have ambient read access to patient health data.
2. Emergency access requires a cryptographic break-glass receipt recorded in `FamilyAccessLog` with:
   - Specific data subject and profile ID
   - Clinical emergency or legal audit rationale
   - Strict time window (maximum 15 minutes)
   - Mandatory multi-party authorization signature

---

## 5. Audit & Compliance Invariants

1. **PDPD Decree 13/2023/NĐ-CP Compliance:** Sensitive personal data (PHR, medications, allergies, clinical notes) is partitioned such that data subject rights (access, portability, deletion) execute with surgical tenant isolation.
2. **Zero-PII Telemetry:** Prometheus metrics, structured logs, and OpenTelemetry spans exclude tenant-specific patient IDs, query strings, and drug names.
3. **Automated Regression Auditing:** The `scripts/ops/audit_cross_tenant_isolation.py` test suite is executed as a mandatory release gate to guarantee that no unscoped SQL queries or admin cross-tenant bypasses enter the codebase.
