# Rollback Plan — PH42 A02 (Constrained Session/Device TTL Schema)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH42_A02 checkout 40e2dfcd0180a5e840d2448378516ee7137f6e06 -- services/control-plane/src/clara_control/db/
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/control-plane/alembic/versions/20260903_0002_admin_sessions_device_ttl.py
   rm -rf artifacts/PH42/A02
   ```
3. Verification:
   ```bash
   git status
   ```
