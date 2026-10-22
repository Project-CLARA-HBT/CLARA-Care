# Rollback Plan — PH10 A02 (Vocabulary Code Mapping Registry)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH10_A02 checkout d17260aa2f70b79fcce8965615d6a2f3068e217d -- services/api/src/clara_api/db/models.py
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/api/alembic/versions/20260906_0068_medical_vocabulary_codes.py
   rm -rf artifacts/PH10/A02
   ```
3. Verification:
   ```bash
   git status
   ```
