# Rollback Plan — PH49 A06 (GLHS Evidence Status Badge)

## Rollback Procedure
1. Remove created component:
   ```bash
   rm -f apps/admin/components/glhs_evidence_badge.tsx
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH49/A06
   ```
3. Verification:
   ```bash
   git status
   ```
