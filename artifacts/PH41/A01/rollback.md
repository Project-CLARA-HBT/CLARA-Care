# Rollback Plan — PH41 A01 (OpenAPI Control Baseline & Health Schema)

## Rollback Procedure
1. Revert router modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH41_A01 checkout f161b49db7c3c54117b8841da3675f92fe19543e -- services/control-plane/src/clara_control/api/router.py
   ```
2. Remove contracts and deliverables:
   ```bash
   rm -f contracts/control-plane/control_v1_openapi.json
   rm -rf artifacts/PH41/A01
   ```
3. Verification:
   ```bash
   git status
   ```
