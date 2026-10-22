# Rollback Plan — PH10 A01 (Event/Assertion/Evidence Typed Contract)

## Rollback Procedure
1. Remove created contract:
   ```bash
   rm -f contracts/clinical/event_assertion_evidence.v1.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH10/A01
   ```
3. Verification:
   ```bash
   git status
   ```
