# Adversarial Audit Report: Job Duplicate-Replay & Queue Starvation Scenario

## Metadata
- **Phase**: PH51 (Job queues, outbox, connectors and webhooks console)
- **Agent**: A10 (Adversarial Reviewer)
- **Date**: 2026-10-22
- **Verdict**: PASS with Verified Guardrails

---

## 1. Adversarial Scenario 1: Flood Duplicate Replay Attack
**Attack Vector**: An adversary sends 1,000 concurrent `POST /control/v1/jobs/{job_id}/replay` requests targeting a dead-lettered job to flood the worker pool and trigger duplicate execution downstream.
**Simulation & Defense Validation**:
- Control-plane domain service (`JobRequeueService`) executes atomic status verification.
- The first request claims transition from `DEAD_LETTER` to `PENDING`.
- All remaining 999 concurrent calls detect state `PENDING` or `RUNNING` and return `ALREADY_ACTIVE` without spawning redundant jobs or resetting attempts.

---

## 2. Adversarial Scenario 2: Worker Starvation & Lease Monopolization
**Attack Vector**: A slow or malfunctioning job type (e.g. OCR scan with infinite recursion) claims worker leases without releasing them, starving time-sensitive webhooks.
**Simulation & Defense Validation**:
- Hard TTL enforcement on `lease_expires_at` (default 30 seconds).
- Exponential backoff jitter on failed attempts prevents thundering herd.
- Maximum attempts ceiling (`max_attempts = 8`) guarantees poison pill ejection to Dead-Letter Queue (DLQ), restoring full worker capacity to healthy queues.

---

## 3. Statutory Gate Verification
- Consent re-evaluation permanently halts replay if patient withdrew consent purposes (`BLOCKED_CONSENT_REVOKED`).
- Egress URL filtering eliminates SSRF attempts against cloud metadata (`169.254.169.254`) and internal RFC 1918 CIDRs.
