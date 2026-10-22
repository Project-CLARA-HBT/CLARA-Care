# Rollback Plan — PH05 A05 (Family / Delegated Authority Restrictions)

## Rollback Procedure
1. Remove created authority module and tests:
   ```bash
   rm -f apps/web/lib/delegated-authority.ts
   rm -f apps/web/lib/delegated-authority.test.ts
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH05/A05
   ```
3. Verification:
   ```bash
   git status
   ```
