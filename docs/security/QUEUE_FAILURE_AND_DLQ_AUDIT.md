# Outbox Queue Failure, Crash Recovery & DLQ Audit (PH09)

## Executive Summary
This security investigation models failure modes in the transactional outbox worker fleet, evaluating worker crash resilience, lease reclamation, and poison pill quarantine.

## Invariant Formalization & Test Results

### 1. Worker Crash & Expired Lease Reclamation
- **Vulnerability:** If an outbox worker claims an event and crashes midway through external network dispatch, the event could remain locked indefinitely.
- **Countermeasure:**
  - Outbox rows feature an indexed `lease_until` timestamp.
  - Active worker queries include `WHERE lease_until IS NULL OR lease_until < NOW()`.
  - Stalled leases are automatically reclaimed by healthy peer workers.

### 2. Poison Pill Quarantine via Dead-Letter Queue (DLQ)
- **Vulnerability:** A malformed payload or permanent external API failure causes infinite retry loops, starving other queued events.
- **Countermeasure:**
  - Events track `attempt_count`. Exceeding `max_attempts` (default 8) automatically updates status to `dead_letter`.
  - Quarantined events are preserved for forensic review and excluded from standard polling loops.
