# PH42 Rollback Procedure

## Scope
Phase PH42 establishes privileged identity OIDC MFA and step-up authorization:
- Session issue, introspection, and step-up API contract (`contracts/control-plane/`, `services/control-plane/src/clara_control/api/router.py`)
- Control admin session model and migration 0002 (`services/control-plane/src/clara_control/db/models.py`, `services/control-plane/alembic/versions/20260903_0002_admin_sessions_device_ttl.py`)
- OIDC token validator & device binding (`services/control-plane/src/clara_control/domain/oidc_validator.py`)
- Legacy admin deprecation headers (`services/api/src/clara_api/core/admin_deprecation.py`, `services/api/src/clara_api/api/v1/endpoints/admin_users.py`)
- Admin sign-in and MFA step-up pages (`apps/admin/app/login/page.tsx`, `apps/admin/app/mfa/page.tsx`)
- Session inventory panel component (`apps/admin/components/session_inventory.tsx`)
- OIDC MFA step-up integration test suite (`services/control-plane/tests/test_oidc_mfa_step_up.py`)
- OIDC MFA and token theft threat model (`docs/security/OIDC_MFA_STEP_UP_THREAT_MODEL.md`)
- Emergency dual-operator root recovery runbook (`docs/runbooks/emergency-root-recovery-dual-operator.md`)
- Adversarial audit & PH42 quality gate (`docs/reports/ph42-oidc-mfa-adversarial-audit.md`, `scripts/ci/ph42_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 40e2dfcd01f3f5db455e2157900212435cdba84d
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH42 --force
   ```
