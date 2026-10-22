# Rollback Plan — PH10 A05 (Source and Acquisition Provenance)

## Rollback Procedure
1. Remove created provenance files:
   ```bash
   rm -f apps/web/lib/clinical-provenance.ts
   rm -f apps/web/lib/clinical-provenance.test.ts
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH10/A05
   ```
3. Verification:
   ```bash
   git status
   ```
