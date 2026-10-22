# Rollback Plan — PH09 A03 (Outbox Retry & DLQ Policy)

## Rollback Procedure
1. Remove created retry policy module:
   ```bash
   rm -f services/api/src/clara_api/glhs/outbox_retry_policy.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH09/A03
   ```
3. Verification:
   ```bash
   git status
   ```
