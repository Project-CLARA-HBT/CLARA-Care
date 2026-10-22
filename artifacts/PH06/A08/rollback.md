# Rollback Plan — PH06 A08 (Stale-Write & Downgrade Threat Model)

## Rollback Procedure
1. Remove created security model and script:
   ```bash
   rm -f docs/security/GLHS_STALE_WRITE_AND_DOWNGRADE_THREAT_MODEL.md
   rm -f scripts/ops/audit_thss_lineage.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH06/A08
   ```
3. Verification:
   ```bash
   git status
   ```
