# Rollback Plan — PH43 A03 (Control-Plane Policy Evaluator)

## Rollback Procedure
1. Remove created evaluator module:
   ```bash
   rm -f services/control-plane/src/clara_control/domain/policy_evaluator.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH43/A03
   ```
3. Verification:
   ```bash
   git status
   ```
