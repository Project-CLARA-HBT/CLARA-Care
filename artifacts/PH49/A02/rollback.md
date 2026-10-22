# Rollback Plan — PH49 A02 (GLHS Provenance Audit Read Model)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH49_A02 checkout 670a050a12e3c035ea6f316d3f2347963be699d7 -- services/control-plane/src/clara_control/db/
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/control-plane/alembic/versions/20260908_0005_glhs_provenance_audit.py
   rm -rf artifacts/PH49/A02
   ```
3. Verification:
   ```bash
   git status
   ```
