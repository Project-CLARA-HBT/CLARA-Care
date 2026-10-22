# PH04 Rollback Procedure

## Scope
Phase PH04 introduces multi-tenant organizations, workspaces, and tenant isolation:
- Organization and Workspace API contracts (`contracts/tenant/`)
- Tenant membership models & migration downgrade integrity (`services/api/src/clara_api/db/models.py`)
- Row-scoped query adapters & tenant isolation (`services/api/src/clara_api/core/tenant.py`)
- Workspace membership invitations & tenant ML boundaries (`services/ml/src/clara_ml/`)
- Web provider/patient organization linking & facility switcher (`apps/web/components/organization/`)
- Mobile tenant organization header propagation (`apps/mobile/lib/core/api_client.dart`)
- Mobile org switch and deep-link test suite (`services/api/tests/test_mobile_org_switching_and_deep_links.py`)
- Cross-tenant isolation regression audit (`docs/security/`)
- Multi-tenant billing boundary privacy audit (`research/billing_tenant_privacy_audit/`)
- Tenant onboarding runbook & PH04 quality gate (`docs/runbooks/tenant-onboarding-and-organization-management.md`, `scripts/ci/ph04_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH04 --force
   ```
