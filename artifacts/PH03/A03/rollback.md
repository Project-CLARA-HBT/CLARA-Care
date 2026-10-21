# PH03-A03 Rollback Procedure

**Phase:** PH03 (Hardening auth và identity)
**Agent:** A03 (Domain + GLHS services)
**Worktree:** `/dev/shm/clara_worktrees/PH03_A03`
**Base Commit:** `3b1072b98350b978b83b7ecec5c35228415759a3`

---

## Rollback Steps

To revert the changes made by subagent A03:

1. **Revert modified code files:**
   ```bash
   git checkout 3b1072b98350b978b83b7ecec5c35228415759a3 -- \
     services/api/src/clara_api/lifemap/profile_scope.py \
     services/api/src/clara_api/glhs/adapters.py
   ```

2. **Remove test file and generated deliverables (if uncommitted):**
   ```bash
   rm -f services/api/tests/test_rbac_profile_scope_idor.py
   rm -rf artifacts/PH03/A03
   ```

3. **Verify clean state:**
   ```bash
   git status
   git diff
   ```

4. **If already committed on branch `phase/ph03-a03`:**
   ```bash
   git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
   ```
