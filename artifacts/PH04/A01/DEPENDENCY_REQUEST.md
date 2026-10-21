# Cross-Agent Dependency Request: Subagent PH04-A01 -> Subagents PH04-A02 & PH04-A03

- **Requesting Agent:** PH04-A01 (API + contract)
- **Target Agents:**
  - PH04-A02 (Data model + migration, Lane: `services/api/src/clara_api/db/;services/api/alembic/versions/`)
  - PH04-A03 (Domain + GLHS services, Lane: `services/api/src/clara_api/glhs/;services/api/src/clara_api/lifemap/;services/api/src/clara_api/phr/;services/api/src/clara_api/compliance/;services/api/src/clara_api/core/`)
- **Phase:** PH04 (Multi-tenant organizations và workspaces)
- **Date:** 2026-10-22

---

## 1. Context & Architecture Background

Subagent **PH04-A01** has finalized the Multi-Tenant Organization & Workspace API design:
1. Pydantic schemas in `services/api/src/clara_api/schemas.py`:
   - `OrganizationRole`, `OrganizationTier`, `OrganizationStatus`, `WorkspaceRole`
   - `OrganizationCreateRequest`, `OrganizationUpdateRequest`, `OrganizationResponse`, `OrganizationListResponse`
   - `OrganizationMemberAddRequest`, `OrganizationMemberUpdateRequest`, `OrganizationMemberResponse`, `OrganizationMemberListResponse`
   - `TenantWorkspaceCreateRequest`, `TenantWorkspaceUpdateRequest`, `TenantWorkspaceResponse`, `TenantWorkspaceListResponse`
   - `TenantAuditLogItem`, `TenantAuditResponse`
2. JSON Schema Contracts in `contracts/organization/`:
   - `organization-tenant-contract.schema.json`
   - `multi-tenant-standards.schema.json`
3. Route handlers and router in `services/api/src/clara_api/api/v1/endpoints/organization.py` mounted at `/api/v1/organizations` in `api/router.py`.

---

## 2. Request to Subagent PH04-A02 (Data Model & Migration)

To persist organizations, tenant memberships, collaborative workspaces, and compliance audit events in PostgreSQL:

1. **Table `organizations`:**
   - Columns: `id` (VARCHAR(36), PK, e.g. `org_...`), `name` (VARCHAR(150), NOT NULL), `slug` (VARCHAR(64), UNIQUE, NOT NULL), `description` (TEXT), `tier` (VARCHAR(32), NOT NULL, default `'standard'`), `status` (VARCHAR(32), NOT NULL, default `'active'`), `contact_email` (VARCHAR(255)), `settings_json` (JSONB/TEXT), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ).
   - Index on `slug`, `status`.

2. **Table `organization_members`:**
   - Columns: `id` (VARCHAR(36), PK, e.g. `mem_...`), `org_id` (VARCHAR(36), FK `organizations.id`, ON DELETE CASCADE), `user_id` (INTEGER, FK `users.id`, NULLABLE for invited external emails), `user_email` (VARCHAR(255), NOT NULL), `role` (VARCHAR(32), NOT NULL), `status` (VARCHAR(32), NOT NULL, default `'active'`), `joined_at` (TIMESTAMPTZ), `created_at` (TIMESTAMPTZ).
   - Unique constraint: `(org_id, user_email)`.

3. **Table `tenant_workspaces`:**
   - Columns: `id` (VARCHAR(36), PK, e.g. `ws_...`), `org_id` (VARCHAR(36), FK `organizations.id`, ON DELETE CASCADE), `name` (VARCHAR(120), NOT NULL), `slug` (VARCHAR(64), NOT NULL), `description` (TEXT), `is_restricted` (BOOLEAN, default FALSE), `is_archived` (BOOLEAN, default FALSE), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ).
   - Unique constraint: `(org_id, slug)`.

4. **Table `tenant_audit_events`:**
   - Columns: `event_id` (VARCHAR(36), PK), `org_id` (VARCHAR(36), NOT NULL, INDEX), `actor_id` (VARCHAR(255), NOT NULL), `action` (VARCHAR(64), NOT NULL), `resource_type` (VARCHAR(64), NOT NULL), `resource_id` (VARCHAR(64), NOT NULL), `metadata_json` (JSONB/TEXT), `timestamp` (TIMESTAMPTZ, NOT NULL).

5. **Alembic Migration:**
   - Ensure migration script defines both forward `upgrade()` and clean, non-empty `downgrade()`.

---

## 3. Request to Subagent PH04-A03 (Domain & Core Adapters)

1. **Row-Scoped Tenant Query Adapter:**
   - Add row-level query helper in `clara_api/core/` (e.g., `tenant_scope.py`) that binds queries to `tenant_id` automatically when executing in a tenant context.
2. **Settings Flag Configuration:**
   - In `services/api/src/clara_api/core/config.py`, expose `feature_multi_tenant_orgs_enabled: bool = Field(default=False, validation_alias="FEATURE_MULTI_TENANT_ORGS_ENABLED")`.
