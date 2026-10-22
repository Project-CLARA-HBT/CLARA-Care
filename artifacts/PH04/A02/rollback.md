# PH04-A02 Rollback Procedure

- **Phase:** PH04
- **Agent:** A02 (Data model + migration)
- **Worktree:** `/dev/shm/clara_worktrees/PH04_A02`
- **Base Commit:** `7f458c915a59a75568e344b670d2f12ce9133a4e`

---

## Rollback Steps

To completely revert the changes made by subagent A02:

1. **Revert documentation annotations on `models.py`:**
   ```bash
   git checkout 7f458c915a59a75568e344b670d2f12ce9133a4e -- services/api/src/clara_api/db/models.py
   ```

2. **Remove generated deliverables and audit artifacts:**
   ```bash
   rm -rf artifacts/PH04/A02
   ```

3. **Verify clean state:**
   ```bash
   git status
   git diff
   ```

4. **If already committed on branch `phase/ph04-a02`:**
   ```bash
   git reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
   ```
