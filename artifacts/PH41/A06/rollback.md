# Rollback Plan — PH41 A06 (Admin Design Tokens & Accessible Shell)

## Rollback Procedure
1. Remove created components:
   ```bash
   rm -rf apps/admin/components
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH41/A06
   ```
3. Verification:
   ```bash
   git status
   ```
