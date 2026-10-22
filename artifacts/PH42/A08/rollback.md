# Rollback Plan — PH42 A08 (OIDC MFA Step-Up & Token Theft Threat Model)

## Rollback Procedure
1. Remove created threat model:
   ```bash
   rm -f docs/security/OIDC_MFA_STEP_UP_THREAT_MODEL.md
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH42/A08
   ```
3. Verification:
   ```bash
   git status
   ```
