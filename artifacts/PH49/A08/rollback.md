# Rollback Plan — PH49 A08 (Lineage Anti-Downgrade & Audit Reconstruction Threat Model)

## Rollback Procedure
1. Remove created threat model:
   ```bash
   rm -f docs/security/GLHS_LINEAGE_ANTI_DOWNGRADE_THREAT_MODEL.md
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH49/A08
   ```
3. Verification:
   ```bash
   git status
   ```
