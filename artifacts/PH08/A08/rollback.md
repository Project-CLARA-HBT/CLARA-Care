# Rollback Plan — PH08 A08 (Postgres TOCTOU Concurrency Audit)

## Rollback Procedure
1. Remove created security report and simulator:
   ```bash
   rm -f docs/security/POSTGRES_TOCTOU_CONCURRENCY_AUDIT.md
   rm -f scripts/ops/simulate_toctou_concurrency.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH08/A08
   ```
3. Verification:
   ```bash
   git status
   ```
