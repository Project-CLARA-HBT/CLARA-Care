# Rollback Plan — PH08 A06 (Staleness UI Rejection Taxonomy)

## Rollback Procedure
1. Remove created taxonomy modules:
   ```bash
   rm -f apps/mobile/lib/core/staleness_taxonomy.dart
   rm -f apps/mobile/test/staleness_taxonomy_test.dart
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH08/A06
   ```
3. Verification:
   ```bash
   git status
   ```
