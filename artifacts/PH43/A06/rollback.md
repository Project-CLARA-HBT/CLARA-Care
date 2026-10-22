# Rollback Plan — PH43 A06 (Permission Diff/Preview Modal)

## Rollback Procedure
1. Remove created component:
   ```bash
   rm -f apps/admin/components/permission_diff_preview.tsx
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH43/A06
   ```
3. Verification:
   ```bash
   git status
   ```
