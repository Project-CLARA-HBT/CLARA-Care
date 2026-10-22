# Rollback Plan — PH42 A01 (Session Lifecycle & Step-Up Contract)

## Rollback Procedure
1. Revert router modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH42_A01 checkout 40e2dfcd0180a5e840d2448378516ee7137f6e06 -- \
     services/control-plane/src/clara_control/api/router.py \
     contracts/control-plane/control_v1_openapi.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH42/A01
   ```
3. Verification:
   ```bash
   git status
   ```
