# Rollback Plan — PH05 A08 (Consent Drift Security Matrix)

## Rollback Procedure
1. Remove created security matrix and script:
   ```bash
   rm -f docs/security/CONSENT_DRIFT_CONCURRENT_SECURITY_MATRIX.md
   rm -f scripts/ops/audit_consent_drift.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH05/A08
   ```
3. Verification:
   ```bash
   git status
   ```
