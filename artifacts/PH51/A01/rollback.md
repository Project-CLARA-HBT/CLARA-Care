# Rollback Plan — PH51 A01 (Admin Job Queue API & Safe DTO)

## Rollback Procedure
1. Revert router modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH51_A01 checkout 7d8840494cf8e30b6c70ea935574516604e4c275 -- \
     services/control-plane/src/clara_control/api/router.py \
     contracts/control-plane/control_v1_openapi.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH51/A01
   ```
3. Verification:
   ```bash
   git status
   ```
