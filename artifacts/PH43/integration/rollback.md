# PH43 Rollback Procedure

## Scope
Phase PH43 establishes platform vs tenant RBAC/ABAC policy enforcement:
- Permission registry contract (`contracts/control-plane/rbac_abac_permission_registry.v1.json`)
- Control role bindings model and migration 0003 (`services/control-plane/src/clara_control/db/models.py`, `services/control-plane/alembic/versions/20260905_0003_control_role_bindings.py`)
- Control policy evaluator service (`services/control-plane/src/clara_control/domain/policy_evaluator.py`)
- Secondary server guard in health adapter (`services/api/src/clara_api/api/v1/endpoints/health_adapter.py`)
- Admin role matrix interface (`apps/admin/app/roles/page.tsx`)
- Permission diff preview modal component (`apps/admin/components/permission_diff_preview.tsx`)
- Multi-tenant RBAC/ABAC contract test suite (`services/control-plane/tests/test_multi_tenant_rbac_abac_contract.py`)
- Zero implicit platform-root PHI proof (`docs/security/ZERO_IMPLICIT_PLATFORM_ROOT_PHI_PROOF.md`)
- Policy inheritance and privacy boundaries specification (`docs/implementation/POLICY_INHERITANCE_AND_PRIVACY_BOUNDARIES.md`)
- Cross-tenant IDOR audit & PH43 quality gate (`docs/reports/ph43-cross-tenant-idor-audit.md`, `scripts/ci/ph43_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 89801b4823bb4b7aab67a8870b365709cbc03339
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH43 --force
   ```
