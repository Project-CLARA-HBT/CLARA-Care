# Rollback Plan — PH06 A02 (THSS Mandatory Admission Decision)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH06_A02 checkout 2370329965f32a7e7df48473e6a2b842ae37580b -- services/api/src/clara_api/db/models.py
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/api/alembic/versions/20260902_0066_thss_mandatory_admission.py
   rm -rf artifacts/PH06/A02
   ```
3. Verification:
   ```bash
   git status
   ```
