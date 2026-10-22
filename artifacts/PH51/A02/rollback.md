# Rollback Plan — PH51 A02 (Job States, Leases & Retry Ledger)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH51_A02 checkout 7d8840494cf8e30b6c70ea935574516604e4c275 -- services/control-plane/src/clara_control/db/
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/control-plane/alembic/versions/20260909_0006_control_job_indexes_and_leases.py
   rm -rf artifacts/PH51/A02
   ```
3. Verification:
   ```bash
   git status
   ```
