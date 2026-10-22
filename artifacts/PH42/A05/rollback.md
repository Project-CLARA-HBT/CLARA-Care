# Rollback Plan — PH42 A05 (Admin Sign-In & MFA Step-Up Flows)

## Rollback Procedure
1. Remove login and MFA pages:
   ```bash
   rm -rf apps/admin/app/login
   rm -rf apps/admin/app/mfa
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH42/A05
   ```
3. Verification:
   ```bash
   git status
   ```
