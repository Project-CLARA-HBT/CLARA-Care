# PH03-A01 Rollback Procedure

- **Phase:** PH03 (Hardening Auth và Identity)
- **Agent:** A01 (API + contract)
- **Worktree:** `/dev/shm/clara_worktrees/PH03_A01`
- **Branch:** `phase/ph03-a01`
- **Base Commit SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`

---

## Rollback Steps

To cleanly revert the deliverables produced by subagent A01:

1. **Delete generated artifact deliverables:**
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH03_A01/artifacts/PH03/A01
   ```

2. **Delete generated contract schemas and tests:**
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH03_A01/contracts/auth
   ```

3. **Reset branch to frozen baseline commit:**
   ```bash
   git -C /dev/shm/clara_worktrees/PH03_A01 checkout phase/ph03-a01
   git -C /dev/shm/clara_worktrees/PH03_A01 reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
   ```

4. **Verify clean worktree state:**
   ```bash
   git -C /dev/shm/clara_worktrees/PH03_A01 status
   git -C /dev/shm/clara_worktrees/PH03_A01 diff
   ```
