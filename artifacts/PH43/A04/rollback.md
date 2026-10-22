# Rollback Plan — PH43 A04 (Secondary Server Guard in Health Adapter)

## Rollback Procedure
1. Revert health adapter modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH43_A04 checkout 89801b4823296c0065793e1140061e56cf574880 -- services/api/src/clara_api/api/v1/endpoints/health_adapter.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH43/A04
   ```
3. Verification:
   ```bash
   git status
   ```
