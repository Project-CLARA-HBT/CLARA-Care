# PH01-A01 Rollback Procedure

**Phase:** PH01  
**Agent:** A01 (API + contract)  
**Worktree:** `/dev/shm/clara_worktrees/PH01_A01`  
**Base Commit:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`  

---

## Rollback Steps

To revert the changes made by subagent A01:

1. **Revert route inventory change:**
   ```bash
   git checkout 2aa9016a57b49b53f1a433d076e1028a6ec45f64 -- services/api/src/clara_api/core/route_inventory.py
   ```

2. **Remove generated deliverables (if uncommitted):**
   ```bash
   rm -rf artifacts/PH01/A01
   ```

3. **Verify clean state:**
   ```bash
   git status
   git diff
   ```

4. **If already committed on branch `phase/ph01-a01`:**
   ```bash
   git reset --hard 2aa9016a57b49b53f1a433d076e1028a6ec45f64
   ```
