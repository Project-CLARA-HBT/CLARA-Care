# Rollback Plan — PH11 A07 (Mobile Consented FHIR Share Integration)

## Rollback Procedure
1. Remove created integration test file:
   ```bash
   rm -f services/api/tests/test_mobile_consented_fhir_share.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH11/A07
   ```
3. Verification:
   ```bash
   git status
   ```
   Ensure working tree is clean and matches base SHA `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`.
