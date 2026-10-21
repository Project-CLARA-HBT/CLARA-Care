# PH02-A01 Rollback Procedure

- **Phase:** PH02
- **Subagent:** A01 (API + contract)
- **Worktree:** `/dev/shm/clara_worktrees/PH02_A01`
- **Base Commit:** `879dc5dcfcaae91b3626e28062043d934294478b`

---

## Rollback Steps

To completely revert all changes introduced by subagent A01:

1. **Revert modified schema file in services/api:**
   ```bash
   git checkout 879dc5dcfcaae91b3626e28062043d934294478b -- services/api/src/clara_api/schemas.py
   ```

2. **Remove newly created contract schema and unit test:**
   ```bash
   rm -rf contracts/agent-execution
   ```

3. **Remove generated deliverables:**
   ```bash
   rm -rf artifacts/PH02/A01
   ```

4. **Verify clean git status:**
   ```bash
   git status
   git diff
   ```

5. **If committed on branch `phase/ph02-a01`:**
   ```bash
   git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
   ```
