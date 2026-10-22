# Rollback Plan — PH43 A05 (Role & Permission Matrix UI)

## Rollback Procedure
1. Remove created page:
   ```bash
   rm -rf apps/admin/app/roles
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH43/A05
   ```
3. Verification:
   ```bash
   git status
   ```
