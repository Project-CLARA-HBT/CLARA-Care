# PH03-A02 Rollback Procedure

**Phase:** PH03 (Hardening auth và identity)
**Agent:** A02 (Data model + migration)
**Worktree:** `/dev/shm/clara_worktrees/PH03_A02`
**Base Commit:** `3b1072b98350b978b83b7ecec5c35228415759a3`

---

## Rollback Steps

To revert the changes made by subagent A02:

1. **Revert database model documentation changes:**
   ```bash
   git checkout 3b1072b98350b978b83b7ecec5c35228415759a3 -- services/api/src/clara_api/db/models.py
   ```

2. **Remove generated deliverables (if uncommitted):**
   ```bash
   rm -rf artifacts/PH03/A02
   ```

3. **Verify clean state:**
   ```bash
   git status
   git diff
   ```

4. **If already committed on branch `phase/ph03-a02`:**
   ```bash
   git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
   ```
