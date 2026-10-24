# Rollback Plan — PH51 A03 (Job Requeue, Idempotency & Consent Recheck)

## Rollback Procedure
1. Remove domain service and artifacts:
   ```bash
   rm -f services/control-plane/src/clara_control/domain/job_requeue_service.py
   rm -rf artifacts/PH51/A03
   ```
2. Verification:
   ```bash
   git status
   ```
