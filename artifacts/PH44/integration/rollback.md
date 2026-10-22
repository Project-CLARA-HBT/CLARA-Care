# PH44 Rollback Procedure

## Scope
Phase PH44 establishes organization lifecycle, onboarding, and workspace federation:
- Tenant REST lifecycle contract (`contracts/control-plane/`, `services/control-plane/src/clara_control/api/router.py`)
- Tenant status lifecycle column and migration 0004 (`services/control-plane/src/clara_control/db/models.py`, `services/control-plane/alembic/versions/20260907_0004_tenant_lifecycle_status.py`)
- Organization lifecycle manager & signed invitations (`services/control-plane/src/clara_control/domain/org_lifecycle.py`)
- Tenant context suspended organization denial (`services/api/src/clara_api/core/tenant.py`)
- Interactive tenant directory UI (`apps/admin/app/tenants/page.tsx`)
- Signed invite modal component (`apps/admin/components/signed_invite_modal.tsx`)
- Tenant suspension and invitation replay test suite (`services/control-plane/tests/test_tenant_suspension_and_invite_replay.py`)
- Multi-tenant bleed & malicious owner threat model (`docs/security/MULTI_TENANT_BLEED_AND_ORG_OWNER_THREAT_MODEL.md`)
- Tenant migration safe dual-read playbook (`docs/implementation/TENANT_MIGRATION_SAFE_DUAL_READ_PLAYBOOK.md`)
- Legacy tenant audit & PH44 quality gate (`docs/reports/ph44-legacy-tenant-vs-governed-org-audit.md`, `scripts/ci/ph44_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard ad75917861972c2ada4c99f7e51700fa0d43813e
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH44 --force
   ```
