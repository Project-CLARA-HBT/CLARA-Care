# Rollback Plan — PH10 A06 (PHR Edit/Review Surfaces)

## Rollback Procedure
1. Remove created widget and test:
   ```bash
   rm -f apps/mobile/lib/widgets/phr_provenance_badge.dart
   rm -f apps/mobile/test/phr_provenance_badge_test.dart
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH10/A06
   ```
3. Verification:
   ```bash
   git status
   ```
