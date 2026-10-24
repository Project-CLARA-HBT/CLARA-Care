# Rollback Plan — PH51 A05 (Job Queues, Outbox & Connector Console)

## Rollback Procedure
1. Remove jobs route and artifacts:
   ```bash
   rm -rf apps/admin/app/jobs
   rm -rf artifacts/PH51/A05
   ```
2. Verification:
   ```bash
   git status
   ```
