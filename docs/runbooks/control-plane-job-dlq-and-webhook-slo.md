# Runbook: Control-Plane Job Queue, DLQ Triage & Webhook SLOs (PH51)

## 1. Scope & Objective
This runbook defines the operational procedures for monitoring background job queues, investigating dead-letter queue (DLQ) entries, executing statutory consent-safe replays, and enforcing Service Level Objectives (SLOs) for external webhook and payment event delivery.

---

## 2. Service Level Objectives (SLOs) & Targets

| Pipeline / Queue | Metric | Target SLO | Warning Threshold | Critical Incident Threshold |
|------------------|--------|------------|-------------------|-----------------------------|
| **Webhook Egress** | Delivery Success Rate | >= 99.9% over 30 days | < 99.5% over 1 hour | < 98.0% over 15 mins |
| **Payment Notification** | End-to-End Delivery Latency | p99 < 3.0s | p99 > 5.0s | p99 > 15.0s |
| **Wearable Sync Outbox** | Queue Draining Lag | < 500 queued events | > 1,000 queued events | > 5,000 queued events |
| **DLQ Dwell Time** | Time to Incident Triage | < 30 minutes | > 1 hour unattended | > 4 hours unattended |

---

## 3. Job State Lifecycle & Lease Dynamics
Background jobs transition through explicit states tracked in `control_job_executions`:
- `PENDING`: Enqueued and waiting for an available worker lease.
- `RUNNING`: Actively leased by a worker pod with an active `lease_expires_at` timestamp.
- `COMPLETED`: Execution succeeded; lease released and `completed_at` populated.
- `FAILED`: Execution failed with an error, but `attempt_count < max_attempts`; rescheduled with exponential backoff.
- `DEAD_LETTER`: `attempt_count >= max_attempts` reached; worker lease revoked, alerts fired.

---

## 4. DLQ Triage & Root Cause Investigation

### Step 1: Query Dead-Letter Queue
Using the Control-Plane REST API or administrative database session:
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8200/control/v1/jobs | jq '.[] | select(.status=="DEAD_LETTER")'
```

### Step 2: Analyze Failure Codes
Common error codes and remediation paths:
- `WEBHOOK_TIMEOUT_EXCEEDED`: Destination partner system is offline or experiencing network partition. Contact partner hospital SRE before replaying.
- `SSRF_ATTEMPT_BLOCKED`: Malicious webhook destination attempted private IP or metadata connection. Do NOT replay. Flag security incident.
- `BLOCKED_CONSENT_REVOKED`: The patient revoked statutory consent purpose while the job was in DLQ. The job must remain terminated.

---

## 5. Manual Replay Execution Protocol

### Step 1: Pre-Replay Statutory Consent Verification
Always verify that the patient's active consent purpose covers the payload intent before replaying:
1. Verify consent records via patient consent audit endpoint.
2. Confirm partner destination status is green.

### Step 2: Trigger Job Replay via Control-Plane API
```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8200/control/v1/jobs/{job_id}/replay
```
The API resets `attempt_count` to 0, transitions status to `PENDING`, and schedules immediate worker pickup.

---

## 6. Worker Crash & Lease Recovery
If a worker node crashes mid-execution:
1. The lease automatically expires when `now() > lease_expires_at`.
2. Peer worker nodes polling the queue detect the expired lease and atomically acquire ownership.
3. The retry attempt counter increments to prevent infinite crash loops.
