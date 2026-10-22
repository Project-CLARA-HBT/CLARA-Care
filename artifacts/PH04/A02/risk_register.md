# Risk Register: PH04-A02 Data Model & Migration Audit

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH04-A02-01** | Architecture / Tenancy Boundary | Fabricating unverified `Organization` or `WorkspaceMember` tables inside `clara_api.db.models` prior to control-plane federation (PH44) creates database schema drift and breaks API data isolation. | High | High | Verified current baseline state: personal workspace models (`WorkspaceFolder`, `WorkspaceChannel`, etc.) remain single-user scoped (`user_id`). Multi-tenant organization entities are reserved for dedicated control plane architecture. | Controlled |
| **RR-PH04-A02-02** | Data Isolation / Tenant Bleed | Relying solely on `GlhsAppliedTransition.tenant_id` as tenancy authority without strict row-level foreign keys or query scoping creates cross-tenant bleed vulnerabilities. | Critical | Medium | `GlhsAppliedTransition.tenant_id` is documented and tested as an idempotency partition (`uq_glhs_applied_trans_idempotency`), NOT an authoritative B2B tenant boundary. B2B isolation requires explicit query adapters (A03) and billing partitioning (A09). | Controlled |
| **RR-PH04-A02-03** | Role Scoping Elevation (BFLA) | `User.role` is currently a platform-global scalar (`normal`, `doctor`, `researcher`, `admin`). A tenant administrator could unintentionally inherit cross-tenant access under legacy RBAC. | Critical | Low | Scoped RBAC/ABAC engine (PH43) must enforce `(tenant_id, user_id, role)` binding; verified that current API models do not allow cross-tenant elevation. | Controlled |
| **RR-PH04-A02-04** | Migration Irreversibility | Future multi-tenant schema additions failing SQLite batch mode or omitting non-empty `downgrade()` functions. | High | Low | Continuous verification via `scripts/ops/check_migration_downgrade.py --strict` (all 64 migrations pass) and SQLite migration roundtrips. | Controlled |
| **RR-PH04-A02-05** | Workspace Collaboration Drift | Misinterpreting existing `workspace_folders` / `workspace_channels` as shared collaborative team spaces rather than personal clinician workspaces. | Medium | Low | Clarified docstrings on `WorkspaceFolder`, `WorkspaceChannel`, and `WorkspaceConversationMeta` confirming strict single-user ownership. | Controlled |

---

## Architectural Invariants Maintained

1. **Deterministic Single-User Workspace Ownership:** Workspace folders, channels, and conversation metadata remain strictly bounded by `user_id` foreign keys with cascade on user deletion.
2. **Reversible Migration Downgrades:** Every migration script in `services/api/alembic/versions` maintains an executable, non-empty `downgrade()` implementation.
3. **Partitioned Idempotency:** Any tenancy identifier (such as `GlhsAppliedTransition.tenant_id`) must be explicitly compounded with operation kind and idempotency keys to prevent cross-tenant key collisions.
4. **No Premature Model Fabrication:** Domain entities belonging to unmerged phases are not introduced without approved migrations and peer subagent contracts.
