# Cross-Tenant Data Protection & Privacy Compliance Assessment

**System:** CLARA-Care Multi-Tenant Health Assistant & Clinical Decision-Support System  
**Legal Basis:**  
- Decree No. 13/2023/NĐ-CP (Personal Data Protection Decree - PDPD) Arts. 2(4), 8, 9, 13, 24  
- Law on Medical Examination and Treatment No. 15/2023/QH15, Art. 8 (Medical confidentiality)  
- Law on Cybersecurity No. 24/2018/QH14, Art. 26 (Data storage and localized protection)  
**Standard Conformance:** ISO/IEC 27001:2022 (A.8.12, A.8.24), ISO/IEC 27701:2019, OWASP Top 10 API Security 2023  
**Review Owner:** Security + Privacy Subagent (PH04_A08)  
**Date:** 2026-10-21  

---

## 1. Regulatory Context & Multi-Tenancy Scope

Under Vietnamese law, clinical and health records are classified as **Sensitive Personal Data** (*Dữ liệu cá nhân nhạy cảm*, PDPD Art. 2(4)). When deployed across multiple clinical organizations (hospitals, ambulatory care networks, diagnostic centers, and individual patient households), the system acts as a multi-tenant processor.

A security breach resulting in cross-tenant leakage (where Clinic A accesses Clinic B's patient roster, or an enterprise administrator inspects individual employee health interactions) violates:
1. **PDPD Art. 8:** Illegal disclosure and unauthorized processing of personal data.
2. **Medical Examination and Treatment Law Art. 8:** Unlawful disclosure of patient medical secrets.
3. **Decree 13/2023/NĐ-CP Art. 13:** Failure to apply specialized organizational and technical safeguards to sensitive personal data.

This compliance assessment verifies that CLARA's multi-tenant architecture strictly enforces mathematical and logical separation between tenants.

---

## 2. Multi-Tenant Separation of Duties & Administrative Containment

### 2.1 The Tenant-Admin Privilege Boundary
A common vulnerability in multi-tenant SaaS architectures is treating the `admin` role as a global wildcard. In CLARA-Care:
- **Tenant Admin Scope:** An actor with `role="admin"` within Tenant A is granted management capabilities strictly bounded to Tenant A's enterprise configuration, user invitations, and organizational settings.
- **Zero Cross-Tenant Superuser Access:** The `admin` role does **not** grant access to Tenant B records under any circumstances.
- **Health Data Decoupling:** In compliance with medical privacy laws, administrative roles do not possess inherent health-data access rights. Even within Tenant A, an administrator cannot inspect a patient's LifeMap, clinical consultations, or medications without explicit patient consent or an audited, break-glass emergency delegation.

### 2.2 Statutory Rights Isolation (PDPD Art. 9)
When a data subject executes a statutory right (such as an Art. 9 DSAR export, erasure, or consent withdrawal):
- Processing is isolated strictly to records associated with the subject's own user account and tenant linkages.
- DSAR extraction routines (`clara.dsar.export.v1`) query explicitly by `owner_user_id` and canonical `profile_id`, ensuring no foreign-tenant metadata or cross-patient health facts are included in the generated export bundle.

---

## 3. Technical Safeguards & Boundary Controls

### 3.1 Logical Data Segregation
All persistent records representing confidential medical or workspace assets implement mandatory tenancy/ownership binding:
1. **Workspace Resources (`WorkspaceFolder`, `WorkspaceChannel`, `WorkspaceNote`, `SessionModel`):** Scoped by `user_id` and organization ID. Lookup queries explicitly verify ownership before returning record state.
2. **Clinical Cases (`ClinicalCase`, `CouncilCase`, `ClinicalWorkflowRun`):** Scoped to the owning clinician and clinical unit. Unauthorized foreign-tenant case requests are rejected fail-closed.
3. **Personal Health Records (`PhrProfile`, `LifeMap*`, `MedicationCourse`):** Governed by `ProfileScope`. Opaque public IDs prevent horizontal enumeration.
4. **Research Trial Data (`KnowledgeSource`, `KnowledgeDocument`):** Scoped to `owner_user_id`. Proprietary datasets cannot be retrieved or synthesized across tenant research units.

### 3.2 Anti-Enumeration & Side-Channel Mitigation
To prevent adversarial actors from inferring the existence of other tenants or patient records:
- **Uniform HTTP 404 Status:** Any attempt by Tenant A to query or mutate an object belonging to Tenant B returns an identical `404 Not Found` response with localized generic detail (`Folder không tồn tại`, `Case không tồn tại`, `Profile not found`).
- **Timing Side-Channel Neutrality:** Database queries execute indexed single-row lookups with constant-time non-existence evaluation to prevent timing-based ID enumeration.

### 3.3 GLHS Commit Kernel State Partitioning
The Governance & Lineage Hardened State (GLHS) transactional engine guarantees:
1. **Tenant-Namespaced Locks:** Advisory lock plans namespace idempotency and policy locks using the format `idempotency:{tenant_id}:{operation_kind}:{idempotency_key}`.
2. **Transition Ledger Segregation:** Every committed state transition records the explicit `tenant_id` alongside the immutable cryptographic digest.
3. **Idempotency Replay Protection:** Replaying an idempotency key submitted by Tenant A inside Tenant B is strictly rejected, preventing cross-tenant transaction poisoning.

---

## 4. Compliance Verification & Regulatory Readiness Matrix

| PDPD / Statutory Mandate | Architectural Safeguard | Operational Verification Tool | Compliance Status |
|---|---|---|---|
| **PDPD Art. 13(1):** Technical protection for sensitive health data | Strict `ProfileScope` and object-level IDOR defenses on all clinical endpoints. | `scripts/ops/audit_cross_tenant_isolation.py` | **COMPLIANT** |
| **PDPD Art. 13(2):** Access control & role authorization | Tenant-admin containment; admin role has no ambient PHR access. | `services/api/tests/test_rbac_profile_scope_idor.py` | **COMPLIANT** |
| **PDPD Art. 24:** Ongoing DPIA & risk management | Living DPIA and cross-tenant threat model documentation. | `docs/compliance/dpia.md`, `docs/security/cross-tenant-isolation-threat-model.md` | **COMPLIANT** |
| **Law 15/2023/QH15 Art. 8:** Medical secrecy preservation | Zero cross-tenant data leakage between clinics and provider organizations. | `research/security_audit/test_security_negative_vectors.py` | **COMPLIANT** |
| **Decree 13/2023/NĐ-CP Art. 8:** Prevention of data exfiltration | Fail-closed non-enumerating 404 responses; no PII telemetry. | `python3 -m evaluation.commitloop.secret_scan --repo-root .` | **COMPLIANT** |

---

## 5. Continuous Governance & Monitoring

1. **Automated CI Regression Testing:** Cross-tenant isolation test suites run on every commit in the PR validation loop.
2. **Secret & Credential Scanning:** Hermetic secret scanner ensures no tenant service keys or multi-tenant database credentials leak into repository commits.
3. **Periodic Multi-Tenant Red-Team Drills:** Automated adversarial audits test boundary enforcement across organizations quarterly.
