# Rollback Plan — PH49 A01 (GLHS Provenance Redacted Read API)

## Rollback Procedure
1. Revert router modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH49_A01 checkout 670a050a12e3c035ea6f316d3f2347963be699d7 -- \
     services/control-plane/src/clara_control/api/router.py \
     contracts/control-plane/control_v1_openapi.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH49/A01
   ```
3. Verification:
   ```bash
   git status
   ```
