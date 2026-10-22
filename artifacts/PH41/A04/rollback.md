# Rollback Plan — PH41 A04 (Authenticated Health API Adapter)

## Rollback Procedure
1. Revert router modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH41_A04 checkout f161b49db7c3c54117b8841da3675f92fe19543e -- services/api/src/clara_api/api/router.py
   ```
2. Remove health adapter and deliverables:
   ```bash
   rm -f services/api/src/clara_api/api/v1/endpoints/health_adapter.py
   rm -rf artifacts/PH41/A04
   ```
3. Verification:
   ```bash
   git status
   ```
