# Rollback Plan — PH05 A07 (Consent Gates & Revocation Tests)

## Rollback Procedure
1. Remove created test file:
   ```bash
   rm -f services/api/tests/test_consent_gates_and_revocation.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH05/A07
   ```
3. Verification:
   ```bash
   git status
   ```
