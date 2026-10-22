# Rollback Plan — PH43 A02 (Role Binding Schema & Org FKs)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH43_A02 checkout 89801b4823296c0065793e1140061e56cf574880 -- services/control-plane/src/clara_control/db/models.py
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/control-plane/alembic/versions/20260905_0003_control_role_bindings.py
   rm -rf artifacts/PH43/A02
   ```
3. Verification:
   ```bash
   git status
   ```
