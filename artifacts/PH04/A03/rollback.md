# PH04-A03 Rollback Procedure

**Phase:** PH04 (Multi-tenant organizations và workspaces)
**Agent:** A03 (Domain + GLHS services)
**Worktree:** `/dev/shm/clara_worktrees/PH04_A03`
**Base Commit:** `7f458c915a59a75568e344b670d2f12ce9133a4e`

---

## Rollback Steps

To cleanly revert the changes made by subagent A03:

1. **Revert modified domain source files:**
   ```bash
   git checkout 7f458c915a59a75568e344b670d2f12ce9133a4e -- \
     services/api/src/clara_api/compliance/dsar.py \
     services/api/src/clara_api/compliance/redaction.py \
     services/api/src/clara_api/compliance/service.py \
     services/api/src/clara_api/core/path_governance.py \
     services/api/src/clara_api/glhs/adapters.py \
     services/api/src/clara_api/glhs/commit_kernel.py \
     services/api/src/clara_api/glhs/commitment_gateway.py \
     services/api/src/clara_api/glhs/gateway.py \
     services/api/src/clara_api/lifemap/profile_scope.py \
     services/api/src/clara_api/phr/audit.py
   ```

2. **Remove newly created domain files and deliverables:**
   ```bash
   rm -f services/api/src/clara_api/core/tenant.py
   rm -rf artifacts/PH04/A03
   ```

3. **Verify clean Git working directory:**
   ```bash
   git status
   git diff
   ```

4. **If already committed to branch `phase/ph04-a03`:**
   ```bash
   git reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
   ```
