# Rollback Plan — PH06 A04 (Lineage Anti-Downgrade Verifier)

## Rollback Procedure
1. Remove created lineage verifier:
   ```bash
   rm -f services/ml/src/clara_ml/lineage_verifier.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH06/A04
   ```
3. Verification:
   ```bash
   git status
   ```
