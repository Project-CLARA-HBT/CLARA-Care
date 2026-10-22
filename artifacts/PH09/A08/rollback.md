# Rollback Plan — PH09 A08 (Queue Failure & Recovery Tests)

## Rollback Procedure
1. Remove created security report and simulator:
   ```bash
   rm -f docs/security/QUEUE_FAILURE_AND_DLQ_AUDIT.md
   rm -f scripts/ops/simulate_queue_recovery.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH09/A08
   ```
3. Verification:
   ```bash
   git status
   ```
