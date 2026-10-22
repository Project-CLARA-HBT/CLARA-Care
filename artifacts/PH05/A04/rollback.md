# Rollback Plan — PH05 A04 (Policy Epoch & Revocation Anchors)

## Rollback Procedure
1. Remove created policy epoch module:
   ```bash
   rm -f services/ml/src/clara_ml/policy_epoch.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH05/A04
   ```
3. Verification:
   ```bash
   git status
   ```
