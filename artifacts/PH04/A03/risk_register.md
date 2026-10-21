# PH04-A03 Risk Register

**Phase:** PH04 (Multi-tenant organizations và workspaces)
**Agent:** A03 (Domain + GLHS services)
**Role:** Domain + GLHS services
**Worktree:** `/dev/shm/clara_worktrees/PH04_A03`
**Date:** 2026-10-22

---

## 1. Identified Risks and Mitigations

| Risk ID | Severity | Likelihood | Impact Area | Risk Description | Remediation / Mitigation Strategy | Status |
|---|---|---|---|---|---|---|
| **RSK-PH04-01** | High | Low | GLHS OCC Kernel | Cross-tenant proposal collision or idempotency key replay across organizations. | Enforced compound unique constraint `(tenant_id, operation_kind, idempotency_key)` and added explicit `tenant_id` filtering in Phase 1 & 7 proposal lookups in `commit_kernel.py`. | **MITIGATED** |
| **RSK-PH04-02** | High | Low | LifeMap Profile Scope | Cross-tenant IDOR where an actor in Organization A queries a health profile in Organization B. | Added `tenant_id` and `organization_id` fields to `ProfileScope`; `resolve_profile_scope` and `require_profile_scope` verify tenant boundaries and raise 404 to avoid enumeration. | **MITIGATED** |
| **RSK-PH04-03** | Medium | Low | Compliance & DSAR | Metadata stripping of structural multi-tenant identifiers or leaking cross-tenant requests in DSAR admin queue. | Added `"tenant_id"` and `"organization_id"` to `_ALLOWED_STRING_KEYS` in `compliance/redaction.py` and implemented tenant-filtered queries in `DsarService.admin_queue`. | **MITIGATED** |
| **RSK-PH04-04** | Medium | Low | PHR Version Snapshots | Cross-tenant version inspection via un-scoped profile queries. | Implemented `scoped_list_versions` in `phr/audit.py`, checking profile tenant ownership before returning historical versions. | **MITIGATED** |
| **RSK-PH04-05** | Low | Low | Path Governance | Multi-agent merge collisions during concurrent execution across 10 subagents. | Formalized `PH04_AGENT_ALLOCATIONS` and validated 100% path lane disjointness (0 collisions across 45 pairs) in `path_governance.py`. | **MITIGATED** |
| **RSK-PH04-06** | Low | Low | Supply-Chain & Zero-ML Coupling | Unintended direct Python imports of `clara_ml` in domain modules. | Validated AST import boundaries via `audit_domain_import_boundaries()`; verified 0 direct imports of `clara_ml`. | **MITIGATED** |

---

## 2. Invariant Checklist

- [x] **RBAC Invariant:** `require_roles(...)` remains strictly intact; route authorization is separated from data scope.
- [x] **Consent Gate:** Medical consent checks in `core/consent.py` and `compliance/` are preserved.
- [x] **Emergency Fast-Path:** Emergency keyword triage in `lifemap/capture_domain.py` is unaffected.
- [x] **FIDES Verification:** Drug/DDI verification gates remain locked.
- [x] **Legal Hard-Guard:** Prescribing/diagnostic prohibition blocks remain active.
- [x] **CSRF Hardening:** Cookie mutation protection and Bearer validation are unchanged.
- [x] **No-PII Telemetry:** Telemetry and compliance events remain strictly free of PII/PHI.
- [x] **Row-Level Tenant Isolation:** All domain queries enforce `tenant_id` boundary checks.
