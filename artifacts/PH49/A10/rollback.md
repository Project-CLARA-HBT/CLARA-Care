# Rollback Plan — PH49 A10 (Lineage Replay & Quality Gate)

## Rollback Procedure
1. Remove created audit report and gate script:
   ```bash
   rm -f docs/reports/ph49-adversarial-replay-lineage-audit.md
   rm -f scripts/ci/ph49_quality_gate.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH49/A10
   ```
3. Verification:
   ```bash
   git status
   ```
