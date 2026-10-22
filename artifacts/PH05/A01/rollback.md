# Rollback Plan — PH05 A01 (Versioned Consent Resource Endpoints)

## Rollback Procedure
1. Revert schemas and auth endpoint changes:
   ```bash
   git -C /dev/shm/clara_worktrees/PH05_A01 checkout 1c626f461ce20f8c050ca161a09d300062b9f939 -- \
     services/api/src/clara_api/schemas.py \
     services/api/src/clara_api/api/v1/endpoints/auth.py
   ```
2. Remove contracts and deliverables:
   ```bash
   rm -rf contracts/consent
   rm -rf artifacts/PH05/A01
   ```
3. Verification:
   ```bash
   git status
   ```
