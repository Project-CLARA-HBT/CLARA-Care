# PH04-A01 Rollback Procedure

- **Phase:** PH04 (Multi-tenant organizations và workspaces)
- **Agent:** A01 (API + contract)
- **Worktree:** `/dev/shm/clara_worktrees/PH04_A01`
- **Branch:** `phase/ph04-a01`
- **Base Commit SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`

---

## 1. Rollback Steps

To cleanly and completely revert the changes introduced by Subagent A01:

1. **Remove generated artifact deliverables:**
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH04_A01/artifacts/PH04/A01
   ```

2. **Remove generated contract schemas and tests:**
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH04_A01/contracts/organization
   ```

3. **Remove newly created organization endpoints:**
   ```bash
   rm -f /dev/shm/clara_worktrees/PH04_A01/services/api/src/clara_api/api/v1/endpoints/organization.py
   ```

4. **Revert modified schema and router files to the frozen baseline:**
   ```bash
   git -C /dev/shm/clara_worktrees/PH04_A01 checkout 7f458c915a59a75568e344b670d2f12ce9133a4e -- \
     services/api/src/clara_api/api/router.py \
     services/api/src/clara_api/api/v1/endpoints/workspace.py \
     services/api/src/clara_api/schemas.py
   ```

5. **Reset git worktree and confirm clean status:**
   ```bash
   git -C /dev/shm/clara_worktrees/PH04_A01 reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
   git -C /dev/shm/clara_worktrees/PH04_A01 status
   git -C /dev/shm/clara_worktrees/PH04_A01 diff
   ```

## 2. Verification of Clean Rollback
After executing the rollback steps above:
- `git status` must show `nothing to commit, working tree clean`.
- `git rev-parse HEAD` must match `7f458c915a59a75568e344b670d2f12ce9133a4e`.
