# Rollback Plan — PH07 A04 (Server-Attested Inference Dispatch)

## Rollback Procedure
1. Remove created dispatcher module:
   ```bash
   rm -f services/ml/src/clara_ml/attested_dispatch.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH07/A04
   ```
3. Verification:
   ```bash
   git status
   ```
