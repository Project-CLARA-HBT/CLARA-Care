# PH04-A01 Risk Register & Multi-Tenant Security Assessment

- **Phase:** PH04 (Multi-tenant organizations và workspaces)
- **Agent:** A01 (API + contract)
- **Worktree:** `/dev/shm/clara_worktrees/PH04_A01`
- **Branch:** `phase/ph04-a01`
- **Base Commit SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`
- **Frozen HEAD SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`
- **Status:** **PASSED**
- **Date:** 2026-10-22

---

## 1. Executive Summary & Audit Profile

Subagent **A01** executed the **organization/workspace API design and audit** for Phase PH04 across:
1. `services/api/src/clara_api/api/v1/endpoints/organization.py` (Tenant organization & collaborative workspace endpoints).
2. `services/api/src/clara_api/api/v1/endpoints/workspace.py` (Existing personal workspace audit & disambiguation).
3. `services/api/src/clara_api/schemas.py` (Multi-tenant Pydantic models, role hierarchies, and lifecycle schemas).
4. `contracts/organization/` (JSON Schema contracts and API standards specification).

### Core Architectural Distinctions:
- **Personal Workspaces (`/api/v1/workspace`):**
  - Scoped 1:1 to single `user_id` (`SessionModel.user_id == user.id`, `WorkspaceFolder.user_id == user.id`).
  - No cross-user collaboration or multi-user access edges.
  - Ownership checked via direct equality; fails closed with 404.
- **Tenant Organizations & Workspaces (`/api/v1/organizations`):**
  - Scoped to tenant organization boundary (`org_id`).
  - Supports collaborative workspaces (`TenantWorkspace`), role hierarchies (`owner`, `admin`, `workspace_lead`, `clinician`, `researcher`, `auditor`, `member`, `viewer`), and member invitation.
  - Anti-IDOR enforcement: Accessing a tenant without membership returns `404 Not Found` rather than `403 Forbidden` to prevent organization enumeration.

---

## 2. Multi-Tenant Threat & Risk Register

| Risk ID | Threat Description | Severity | Likelihood | Impact | Current Controls & Defenses | Residual Gap / Next Phase Recommendation |
|---|---|---|---|---|---|---|
| **RSK-TENANT-01** | **Cross-Tenant IDOR & Resource Discovery** | **CRITICAL** | High | Critical | • `_check_tenant_access` fails closed with uniform `404 Not Found` for non-members.<br>• Identical error message and status code regardless of whether `org_id` exists. | In DB migration phase, enforce composite unique constraints and row-level security (RLS) in PostgreSQL. |
| **RSK-TENANT-02** | **Tenant Identifier Spoofing via Headers** | **HIGH** | Medium | High | • Tenant access is derived exclusively from verified JWT authentication token and verified membership store.<br>• External client-supplied `X-Tenant-ID` headers are ignored for authorization. | Reverse proxy (Nginx/Cloudflare) must explicitly strip incoming `X-Tenant-ID` or `X-Org-ID` headers from untrusted origins. |
| **RSK-TENANT-03** | **PII/PHI Exposure in Audit Journals** | **HIGH** | Medium | High | • `TenantAuditLogItem` enforces non-PII attributes (`actor_id`, `action`, `resource_type`, `resource_id`, opaque metadata).<br>• Zero patient identifiers or clinical consultation text in audit payload. | Subagent A08/A09 to verify automated scrubbing on any custom metadata dictionary fields. |
| **RSK-TENANT-04** | **Orphaned Organization via Last Owner Removal** | **MEDIUM** | Low | High | • Explicit invariant check in `remove_organization_member`: Cannot remove the last active owner of an organization (returns 400 Bad Request). | Add transfer-of-ownership endpoint when organization owners depart. |
| **RSK-TENANT-05** | **Tenant Namespace Collision via Slugs** | **LOW** | Medium | Medium | • URL slug uniqueness validated at creation time (`409 Conflict`).<br>• `_slugify()` sanitizes names to lowercase alphanumeric + hyphens. | Reserved words allowlist (e.g., `admin`, `api`, `auth`, `system`) should be enforced on organization slug creation. |
| **RSK-TENANT-06** | **State Inconsistency Between Personal & Tenant Workspaces** | **MEDIUM** | Low | Low | • Explicitly segregated route paths: `/api/v1/workspace` (personal) vs `/api/v1/organizations/{org_id}/workspaces` (collaborative).<br>• Documented in schemas and contracts. | Maintain clear UI IA separation in Web (`apps/web`) and Flutter (`apps/mobile`). |

---

## 3. Defense-in-Depth Verification Matrix

1. **Gateway Tier:** Authenticated JWT token verified via `USER_ROLE_DEP` (`require_roles("normal", "researcher", "doctor", "admin")`).
2. **Endpoint Tier:** `_check_tenant_access(org_id, user, token, required_roles)` validates actor membership and role.
3. **Anti-IDOR Tier:** Uniform `404 Not Found` returned on non-existent or unpermitted organizations/workspaces.
4. **Audit Tier:** Every administrative action (`create`, `update`, `member.invite`, `member.remove`, `workspace.archive`) dispatched to non-PHI audit ledger.
