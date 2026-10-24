# PH51 Integration Demo — Job Queues, Outbox & Connector Console

## Scenario 1: Inspecting Queued Tasks & Outbox Relay
1. Start control plane:
   ```bash
   uvicorn clara_control.main:app --port 8200
   ```
2. Query job list via control plane API:
   ```bash
   curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8200/control/v1/jobs
   ```

## Scenario 2: Dead-Letter Queue Triage & Safe Replay
1. Inspect dead-lettered job:
   ```bash
   curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8200/control/v1/jobs/job-dlq-5102
   ```
2. Trigger replay:
   ```bash
   curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8200/control/v1/jobs/job-dlq-5102/replay
   ```
3. Job status resets to `PENDING` with 0 attempts and active worker pickup.
