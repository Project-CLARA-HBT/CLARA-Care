# Rollback Plan — PH44 A02 (Org Slug & Lifecycle Status Migration)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH44_A02 checkout ad759178619bc5bebe867d34199c93a0bcf5f1cf -- services/control-plane/src/clara_control/db/models.py
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/control-plane/alembic/versions/20260907_0004_tenant_lifecycle_status.py
   rm -rf artifacts/PH44/A02
   ```
3. Verification:
   ```bash
   git status
   ```
