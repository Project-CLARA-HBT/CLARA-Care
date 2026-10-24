# Rollback Plan — PH51 A04 (Health API Outbox & Connector Status Adapters)

## Rollback Procedure
1. Revert changes to API and ML packages:
   ```bash
   git -C /dev/shm/clara_worktrees/PH51_A04 checkout 7d8840494cf8e30b6c70ea935574516604e4c275 -- \
     services/api/src/clara_api/ \
     services/ml/src/clara_ml/
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH51/A04
   ```
3. Verification:
   ```bash
   git status
   ```
