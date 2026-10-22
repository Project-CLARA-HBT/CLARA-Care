# Runbook: Outbox Worker Operations, DLQ Replay & Retention (PH09)

## 1. Overview
Governs operational monitoring, dead-letter queue (DLQ) investigation, and historical event retention for the Transactional Outbox subsystem.

## 2. Queue Health Metrics & Alerts
- **Pending Lag Alarm:** Alert if pending event count exceeds 500 records.
- **DLQ Alarm:** Alert immediately if any event transitions to `dead_letter` status.

## 3. DLQ Investigation & Replay Procedure
When an alert fires for an event in `dead_letter` status:
1. **Inspect Event Details:**
   ```sql
   SELECT event_id, event_type, last_error_code, attempt_count, dead_lettered_at
   FROM lifemap_outbox_events
   WHERE status = 'dead_letter';
   ```
2. **Determine Root Cause:**
   - If downstream subscriber was down: Issue replay.
   - If payload was corrupt (poison pill): Fix bug in producer and mark event resolved.
3. **Replay Command:**
   ```bash
   python3 -m clara_api.lifemap.replay_outbox --event-id "evt-12345"
   ```

## 4. Retention & Archival Protocol
- **Published Events:** Retained in live table for 14 days, then archived to partitioned cold storage.
- **Dead-Letter Events:** Retained for 90 days for forensic analysis.
