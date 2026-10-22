# Rollback Plan — PH44 A05 (Org Lifecycle & Settings UI)

## Rollback Procedure
1. Revert tenants page:
   ```bash
   git -C /dev/shm/clara_worktrees/PH44_A05 checkout ad759178619bc5bebe867d34199c93a0bcf5f1cf -- apps/admin/app/tenants/page.tsx
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH44/A05
   ```
3. Verification:
   ```bash
   git status
   ```
