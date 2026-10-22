# Rollback Plan — PH40 A04 (ML Provider Boundaries & Safe Fallbacks)

## Rollback Procedure
1. Remove created ML boundary audit module:
   ```bash
   rm -f services/ml/src/clara_ml/llm/audit_boundaries.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH40/A04
   ```
3. Verification:
   ```bash
   git status
   ```
