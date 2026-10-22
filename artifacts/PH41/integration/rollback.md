# PH41 Rollback Procedure

## Scope
Phase PH41 builds the separate admin control-plane foundational architecture:
- OpenAPI control baseline & health schema (`contracts/control-plane/`, `services/control-plane/src/clara_control/api/`)
- Control-plane database schema & migration 0001 (`services/control-plane/alembic/versions/20260901_0001_control_plane_initial.py`)
- Service-token gateway & tenant governor (`services/control-plane/src/clara_control/domain/`)
- Authenticated health API adapter (`services/api/src/clara_api/api/v1/endpoints/health_adapter.py`)
- Independent apps/admin Next.js route tree (`apps/admin/app/`)
- Admin design tokens & accessible shell (`apps/admin/components/`)
- Forbidden cross-origin integration test suite (`services/control-plane/tests/test_forbidden_cross_origin_admin.py`)
- Control plane network & SSO threat model (`docs/security/CONTROL_PLANE_NETWORK_AND_SSO_THREAT_MODEL.md`)
- ADR on control/data plane segregation & deployment runbook (`docs/implementation/ADR_CONTROL_PLANE_DATA_PLANE_SEGREGATION.md`)
- Hostile route audit & PH41 quality gate (`docs/reports/ph41-hostile-admin-route-audit.md`, `scripts/ci/ph41_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard f161b49db767c1e3d4e33c218305ee54056bcdfd
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH41 --force
   ```
