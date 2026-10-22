# Rollback Plan — PH05 A06 (Consent Explanation UX)

## Rollback Procedure
1. Remove created widget and test:
   ```bash
   rm -f apps/mobile/lib/widgets/consent_explanation_sheet.dart
   rm -f apps/mobile/test/consent_explanation_ux_test.dart
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH05/A06
   ```
3. Verification:
   ```bash
   git status
   ```
