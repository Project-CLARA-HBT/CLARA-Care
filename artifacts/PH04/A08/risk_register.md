# Risk Register: Cross-Tenant Isolation & Multi-Tenant Boundaries

**Phase:** PH04  
**Subagent:** A08  
**Role:** Security + privacy  
**Last Updated:** 2026-10-21  

---

## 1. Risk Matrix

| Risk ID | Vulnerability / Threat | Likelihood | Impact | Risk Level | Mitigation & Compensating Controls | Residual Risk | Owner |
|---|---|---|---|---|---|---|---|
| **RSK-TEN-01** | **Admin Users List Lacks Organization Scoping** (`TEN-ADM-03`): `list_admin_users()` queries `User` table without organization predicate. | MEDIUM | HIGH | **HIGH** | In PH04 A01/A02, introduce `organization_id` on `User` / membership schema and filter user list by caller's organization. | LOW | API Core / Auth |
| **RSK-TEN-02** | **Clinical Patient Roster Cross-Tenant Leakage** (`TEN-ROST-01`): `get_clinical_patient_roster()` queries `PhrProfile` globally without tenant filter. | MEDIUM | HIGH | **HIGH** | Bind patient roster queries to clinician's authorized organization membership or active primary care team; maintain masked labels (`BN-XXXXXXXX`). | LOW | Clinical Workbench |
| **RSK-TEN-03** | **Admin Audit Log Visibility Bleed** (`TEN-AUD-01`): `list_admin_audit()` queries `AdminAuditRecord` globally without tenant partition. | LOW | MEDIUM | **MEDIUM** | Partition `AdminAuditRecord` by `organization_id` / `tenant_id` so organization admins only see local admin actions. | NEGLIGIBLE | Observability |
| **RSK-TEN-04** | **Clinical Feedback Cross-Clinic Visibility** (`TEN-FDB-01`): `list_clinical_feedback()` queries feedback without tenant partition. | LOW | MEDIUM | **MEDIUM** | Add `organization_id` to `ClinicalFeedback` model and scope query by reporting organization. | LOW | Clinical Ops |
| **RSK-TEN-05** | **Cross-Tenant IDOR via Shared Object IDs** (`THR-TEN-01`): Malicious user in Tenant A guessing integer IDs of Tenant B folders/cases. | LOW | HIGH | **LOW** | Enforced: All object helpers (`_get_owned_folder`, `_get_owned_case`, etc.) enforce strict `user_id == user.id` predicates with 404 fail-closed. | NEGLIGIBLE | Security + API |
| **RSK-TEN-06** | **GLHS Idempotency Key Hijack Across Tenants** (`THR-TEN-04`): Actor in Tenant B replaying Tenant A's commit key to block transitions. | LOW | HIGH | **LOW** | Enforced: GLHS lock plan and replay detection strictly namespace keys: `idempotency:{tenant_id}:{operation_kind}:{idempotency_key}`. | NEGLIGIBLE | GLHS Core |
| **RSK-TEN-07** | **Identifier Enumeration via 403 vs 404 Timing** (`THR-TEN-03`): Attacker probing endpoints to distinguish non-existent from foreign IDs. | LOW | LOW | **LOW** | Enforced: Uniform HTTP 404 responses with identical non-leaking messages returned for foreign and non-existent IDs. | NEGLIGIBLE | Security |

---

## 2. Risk Treatment & Governance Plan

1. **Immediate Release Gate:** Incorporate `scripts/ops/audit_cross_tenant_isolation.py` into the automated CI quality gate (`scripts/ci/ph04_quality_gate.py`) to prevent unscoped SQL queries.
2. **Phase Handoff to PH04 Feature Agents:**
   - Handoff `RSK-TEN-01` to A01/A02 (organization and workspace schema/API design).
   - Handoff `RSK-TEN-02` to A05 (provider/patient organization linking).
   - Handoff `RSK-TEN-03` and `RSK-TEN-04` to A10 (tenant administration playbook).
3. **Statutory Assurance:** Zero Personal Health Data (PHI) or authentication secrets are exposed across tenant boundaries under current production controls.
