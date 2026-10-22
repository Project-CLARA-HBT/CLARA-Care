# Rollback Plan — PH41 A02 (Control-Plane Schema & Migration Plan)

## Rollback Procedure
1. Remove migration and schema plan:
   ```bash
   rm -f services/control-plane/alembic/versions/20260901_0001_control_plane_initial.py
   rm -f services/control-plane/src/clara_control/db/schema_plan.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH41/A02
   ```
3. Verification:
   ```bash
   git status
   ```
