# Rollback Plan — PH51 A07 (Worker Death, Duplicate & TTL Expiration Tests)

## Rollback Procedure
1. Remove integration test and artifacts:
   ```bash
   rm -f services/control-plane/tests/test_worker_death_ttl_and_duplicate_queue.py
   rm -rf artifacts/PH51/A07
   ```
2. Verification:
   ```bash
   git status
   ```
