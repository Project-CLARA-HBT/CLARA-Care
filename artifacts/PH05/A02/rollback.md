# Rollback Plan — PH05 A02 (Consent Snapshot Persistence)

## Rollback Procedure
1. Revert models change:
   ```bash
   git -C /dev/shm/clara_worktrees/PH05_A02 checkout 1c626f461ce20f8c050ca161a09d300062b9f939 -- services/api/src/clara_api/db/models.py
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/api/alembic/versions/20260827_0065_consent_policy_snapshots.py
   rm -rf artifacts/PH05/A02
   ```
3. Verification:
   ```bash
   git status
   ```
