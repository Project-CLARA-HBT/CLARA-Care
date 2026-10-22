# Rollback Plan — PH42 A04 (Legacy Admin Deprecation & Sunset Headers)

## Rollback Procedure
1. Revert admin users endpoint:
   ```bash
   git -C /dev/shm/clara_worktrees/PH42_A04 checkout 40e2dfcd0180a5e840d2448378516ee7137f6e06 -- services/api/src/clara_api/api/v1/endpoints/admin_users.py
   ```
2. Remove deprecation module and deliverables:
   ```bash
   rm -f services/api/src/clara_api/core/admin_deprecation.py
   rm -rf artifacts/PH42/A04
   ```
3. Verification:
   ```bash
   git status
   ```
