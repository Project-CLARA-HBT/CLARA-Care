# Runbook: Multi-Tenant Organization Onboarding, Workspace Lifecycle & Cross-Tenant Isolation

**Status:** ACTIVE OPERATIONAL RUNBOOK · REGRESSION-LOCKED TO CONTRACT SPEC  
**Audience:** Platform Reliability Engineers, Platform Operations Lead, Security & Compliance Officers  
**Scope:** Multi-Tenant Architecture, Tenant Scoping, Organization & Workspace Lifecycles, Data Isolation, Cross-Tenant Boundary Enforcement  
**Phase Verification Anchor:** PH04 / Subagent A10  

---

## 1. Multi-Tenant Architectural Principles & Invariants

CLARA-Care is a safety-first Vietnamese clinical and medical assistant platform supporting multi-tenant deployment models (e.g., individual healthcare clinics, hospital networks, diagnostic centers, research cohorts, and family care units). Multi-tenancy must never compromise data boundaries, clinical safety, patient privacy, or auditability.

### 1.1 Strict Isolation Invariants
1. **Zero Cross-Tenant Leakage:** An actor authenticating within Tenant $T_A$ must never read, mutate, discover, or infer the existence of data belonging to Tenant $T_B$.
2. **Uniform Denial & Non-Enumeration (Anti-IDOR):** Queries or requests referencing nonexistent resources or cross-tenant resources must fail closed with identical status codes (`404 Not Found`), identical error payloads, and uniform timing profiles to prevent tenant enumeration and identifier brute-forcing.
3. **Defense-in-Depth Enforcement:**
   - **Network & Gateway Tier:** Tenant context (`tenant_id` / `org_id`) extracted from authenticated token claims or validated domain routing headers; client-supplied unverified tenant headers are strictly stripped.
   - **Application & Service Tier:** Row-level and workspace query adapters enforce tenant filtering at the query construction boundary.
   - **Database & Storage Tier:** Explicit tenant foreign keys (`tenant_id`, `org_id`), composite unique constraints including `tenant_id`, and isolated partition schemes where configured.
   - **Cache & Key-Value Tier:** Redis and cache keys strictly namespaced (`{tenant_id}:{subsystem}:{key}`).
4. **Administrative Demarcation:** System `admin` access is strictly separated from tenant-local administrative roles (`org_admin`, `workspace_lead`). System-level administration requires explicit break-glass auditing and never bypasses patient consent gates or data encryption policies.
5. **No-PII Telemetry:** Logs, metrics, trace tags, and operational events must record opaque tenant identifiers (`tenant_id`), anonymized audit hashes, and non-PHI operational counts only. Plaintext names, emails, medical records, and drug lists are strictly excluded.

---

## 2. Organization & Workspace Lifecycle

### 2.1 Entity Hierarchy
```
Platform Master Root
└── Tenant / Organization (org_id / tenant_id)
    ├── Organization Settings & Policy Envelopes
    ├── Organization Memberships (User <-> Org Role Mapping)
    ├── Workspaces (Department, Ward, Clinical Study, or Care Unit)
    │   ├── Workspace Memberships (Role: workspace_admin, clinician, member, viewer)
    │   ├── Workspace Folders & Channels
    │   ├── Workspace Conversations & Clinical Session Metadata
    │   └── Workspace Shared Notes & Export Projections
    └── Tenant-Scoped Clinical Commitments & Audit Ledgers
```

### 2.2 Roles and Privileges Matrix
| Role | Scope | Permitted Actions | Prohibited Actions |
|---|---|---|---|
| **System Admin** | Global / Platform | System provisioning, tenant lifecycle management, infrastructure health, break-glass audit. | Direct PHI queries without break-glass consent ticket; cross-tenant session bridging. |
| **Org Admin** | Organization ($T$) | Workspace provisioning, member invitation within org, org-wide policy configuration, compliance exports. | Accessing other organizations; mutating clinical records outside assigned clinical duties. |
| **Workspace Lead** | Workspace ($W \subset T$) | Channel management, folder structuring, workspace member assignment, workflow triggers. | Modifying org billing; cross-workspace data migration without review approval. |
| **Clinician / Member** | Workspace ($W \subset T$) | Clinical conversation execution, patient consultation note authoring, encounter recording. | Administrative re-configuration; member removal; export of unmasked data. |
| **Viewer / Auditor** | Workspace ($W \subset T$) | Read-only inspection of governed clinical records and audit journals within scope. | Any state mutation; inviting users; unmasking restricted PHI. |

---

## 3. Step-by-Step Tenant Onboarding Runbook

### Phase 1: Pre-Onboarding Validation & Verification
Before provisioning a new tenant organization:
1. Verify legal charter, compliance requirements, and Business Associate Agreement (BAA) / Vietnamese NDPE compliance agreements.
2. Allocate a unique, immutable tenant identifier (`tenant_id`: lowercase alphanumeric, 3 to 32 characters, regex `^[a-z0-9_-]{3,32}$`).
3. Verify database connectivity and schema migration status:
   ```bash
   python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions
   ```

### Phase 2: Tenant Organization Provisioning
Execute the tenant provisioning sequence:
1. **Initialize Organization Master Record:**
   - Create organization record with primary attributes: `tenant_id`, `legal_name`, `slug`, `region` (`ap-southeast-1` / local), and `tier`.
   - Initialize cryptographic signing seed or tenant-specific encryption key version where dedicated KMS encryption is required.
2. **Seed Default Organization Workspaces:**
   - Create primary default workspace (e.g., `slug="general"`, `display_name="General Clinical Workspace"`).
   - Set workspace isolation boundaries and default retention policies (default: 365 days or regulatory guideline).
3. **Bootstrap Initial Organization Administrator:**
   - Create or link the initial `org_admin` user account.
   - Dispatch invitation token via secure out-of-band channel (one-time cryptographic hash, 24-hour expiration).
   - Require immediate password setup and multi-factor authentication enrollment before granting access.

### Phase 3: Tenant Verification & Isolation Smoke Testing
Run verification checks before cutting over production traffic:
1. **Isolation Check:** Verify that the newly provisioned tenant cannot access baseline default data or other test tenants.
2. **Idempotency Check:** Confirm that re-executing the onboarding transaction with identical `tenant_id` fails safely with `409 Conflict` and produces zero duplicate artifacts.
3. **Audit Trail Verification:** Ensure creation events are committed to `compliance_events` with non-PHI metadata.

---

## 4. Tenant Migration, Deprecation & Offboarding Runbook

### 4.1 Migration Between Workspaces or Tiers
When migrating tenant data or upgrading an organization:
1. **Enter Maintenance Mode:** Set tenant status flag `status="maintenance"`. Active mutating API calls will return `503 Service Unavailable` with `Retry-After: 300`.
2. **Execute Point-in-Time Snapshot:** Create an immutable backup of tenant database partitions and Redis state.
3. **Execute Partitioned Migration:** Run tenant migration scripts scoped specifically to the target `tenant_id`.
4. **Perform Checksum Integrity Validation:** Verify row counts, cryptographic content digests, and relation integrity across source and target.
5. **Lift Maintenance Mode:** Set tenant status to `status="active"`.

### 4.2 Tenant Offboarding & DSAR Data Purge
When a tenant organization terminates service:
1. **Revoke All Active Sessions:**
   - Invalidate all issued access and refresh tokens for all users associated with the tenant.
   - Purge tenant session keys from Redis:
     ```bash
     # Flush tenant-namespaced Redis cache keys
     redis-cli --scan --pattern "tenant:${TENANT_ID}:*" | xargs -r redis-cli del
     ```
2. **Enforce Archival Quarantine:**
   - Transition organization state to `status="quarantined"` for the contractually mandated retention window (e.g., 30 days).
   - Restrict access to compliance officers only.
3. **Cryptographic Deletion & Hard Purge:**
   - Following quarantine expiry, execute cryptographically verified purge of all tenant clinical records, files, and workspace items.
   - Record an immutable `PrivacyAuditReceipt` containing `artifact_digest` and execution timestamps with zero PHI.

---

## 5. Security & Isolation Incident Response Playbook

### Scenario 1: Suspected Cross-Tenant Data Leakage
1. **Immediate Containment:**
   - Place affected tenant(s) into restricted isolation mode:
     ```bash
     # Disable tenant via administration CLI / config override
     python3 -c "from clara_api.core.config import get_settings; print('Active Isolation Gate Engaged')"
     ```
2. **Token Revocation:**
   - Revoke all credentials issued to the suspect user or tenant cluster.
3. **Forensic Audit:**
   - Inspect query logs for cross-tenant query signatures where `token.tenant_id != resource.tenant_id`.
   - Analyze `compliance_events` and `family_access_logs`.
4. **Remediation:**
   - Patch query adapter or RBAC filter.
   - Run `scripts/ci/ph04_quality_gate.py` to confirm zero regressions.

### Scenario 2: Tenant Identifier Spoofing Attempt
1. Inspect gateway headers to confirm reverse proxy strips external `X-Tenant-ID` or `X-Org-ID` headers.
2. Confirm API routes strictly derive tenant authorization from verified JWT claims (`token.tenant_id`) rather than request query parameters or client body hints.

---

## 6. Verification Commands & Operational Checklist

| Inspection Step | Command / Validation Procedure | Expected Result |
|---|---|---|
| Migration Downgrades | `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions` | `OK: every migration defines a downgrade()` |
| AST Bytecode Safety | `python3 -m compileall -q services/api/src scripts/ci/` | Exit Code 0, zero syntax errors |
| Path ACL Boundaries | `python3 scripts/ci/check_agent_path_acl.py --agent-id A10 --phase-id PH04` | `PATH ACL CHECKER — PASSED` |
| PH04 Quality Gate | `python3 scripts/ci/ph04_quality_gate.py` | `PH04 QUALITY GATE VERDICT: PASSED` |
