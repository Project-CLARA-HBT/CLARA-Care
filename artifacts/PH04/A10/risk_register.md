# Risk Register — PH04 Multi-Tenant Organizations & Workspaces (Subagent A10)

**Phase:** PH04 — Multi-tenant Organizations & Workspaces  
**Subagent:** Subagent A10 — Adversarial Audit + Integration Proposals  
**Worktree:** `/dev/shm/clara_worktrees/PH04_A10`  
**Branch:** `phase/ph04-a10`  
**Base SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`  
**Status:** ACTIVE AUDIT REGISTER · GATE VERIFIED  

---

## 1. Scope & Objective

Phase PH04 introduces multi-tenant organizational hierarchies, workspace grouping, and row-level tenant boundary adapters. This register analyzes adversarial attack vectors, tenant boundary erosion risks, and failure modes across tenant lifecycle operations.

---

## 2. Identified Risks & Automated Mitigations

| Risk ID | Category | Severity | Likelihood | Impact | Threat & Vulnerability Summary | Mitigations & Verification Controls |
|---|---|---|---|---|---|---|
| **RISK-PH04-01** | Multi-Tenancy / IDOR | **CRITICAL** | Medium | Critical | **Cross-Tenant Data Exposure via IDOR**<br>An authenticated user in Tenant A accesses or mutates clinical files, conversations, or profiles belonging to Tenant B by manipulating entity public IDs. | **Mitigated in `profile_scope.py` & Workspace Adapters**:<br>Queries strictly bind `tenant_id` / `user_id` from verified token claims. Requests for nonexistent or cross-tenant resources return uniform `404 Not Found` with zero information disclosure. Verified by `test_uniform_404_error_structure`. |
| **RISK-PH04-02** | Gateway / Spoofing | **HIGH** | Medium | High | **Tenant Header Forgery (`X-Tenant-ID`)**<br>Malicious actor forging `X-Tenant-ID` or `X-Org-ID` headers to trick the backend into querying a victim tenant's namespace. | **Mitigated in Reverse Proxy & RBAC Middleware**:<br>Gateway strips external unauthenticated tenant headers. Tenant context is derived strictly from validated, non-revoked cryptographic JWT claims. |
| **RISK-PH04-03** | Concurrency / Outbox | **HIGH** | Low | High | **Idempotency Collision Across Tenants**<br>Two different tenants generating identical transaction idempotency keys (e.g. `tx_001`), leading to cross-tenant transaction blocking or state pollution. | **Mitigated in `GlhsAppliedTransition` & `commit_kernel.py`**:<br>Unique constraints and Redis lock keys strictly partition by `tenant_id`: `idempotency:{tenant_id}:{operation_kind}:{idempotency_key}`. Verified by `test_cross_tenant_idempotency_key_partitioning`. |
| **RISK-PH04-04** | Privacy / Compliance | **HIGH** | Medium | High | **Cross-Tenant Contamination in Shared Cache**<br>Redis cache keys missing tenant namespace prefixes, allowing cached patient summaries to be returned to unauthorized users in other organizations. | **Mitigated in Cache Namespace Standards & Runbook §1.1**:<br>Mandatory namespacing pattern `{tenant_id}:{subsystem}:{key}` enforced for all cache operations. Purging routines operate strictly per-tenant pattern. |
| **RISK-PH04-05** | Migration / Ops | **HIGH** | Low | High | **Destructive Migration without Rollback Capability**<br>Database migration introducing tenant foreign keys that cannot be cleanly downgraded, locking deployment. | **Mitigated in `check_migration_downgrade.py`**:<br>Automated check in CI requires all Alembic migrations to supply non-empty, functional `downgrade()` methods. Verified across all 64 migrations. |
| **RISK-PH04-06** | Telemetry / Privacy | **HIGH** | Low | High | **PII Leakage in Multi-Tenant Audit Events**<br>Audit records capturing free-text patient names or clinical terms under tenant audit dashboards. | **Mitigated in `ComplianceEvent` & `FamilyAccessLog`**:<br>Strict PII-free schema: actors and subjects are stored as SHA-256 hashed digests; metadata enforces structured reason codes only. |

---

## 3. Residual Risk Assessment

With the adoption of the multi-tenant onboarding runbook, strict token-derived tenant binding, uniform 404 anti-enumeration responses, and automated verification via `scripts/ci/ph04_quality_gate.py`, the residual risk of cross-tenant exposure is controlled and compliant with platform security baselines.
