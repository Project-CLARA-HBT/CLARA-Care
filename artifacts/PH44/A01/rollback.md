# Rollback Plan — PH44 A01 (Tenant Organization REST Contract)

## Rollback Procedure
1. Revert router modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH44_A01 checkout ad759178619bc5bebe867d34199c93a0bcf5f1cf -- \
     services/control-plane/src/clara_control/api/router.py \
     contracts/control-plane/control_v1_openapi.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH44/A01
   ```
3. Verification:
   ```bash
   git status
   ```
