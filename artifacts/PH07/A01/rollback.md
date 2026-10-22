# Rollback Plan — PH07 A01 (D1 Projection Digest & Schema)

## Rollback Procedure
1. Revert schemas modification:
   ```bash
   git -C /dev/shm/clara_worktrees/PH07_A01 checkout e8533cb029a1470ce2d1bc027a421b47664871c5 -- services/api/src/clara_api/schemas.py
   ```
2. Remove contract and deliverables:
   ```bash
   rm -f contracts/glhs/d1_projection_contract.v1.json
   rm -rf artifacts/PH07/A01
   ```
3. Verification:
   ```bash
   git status
   ```
