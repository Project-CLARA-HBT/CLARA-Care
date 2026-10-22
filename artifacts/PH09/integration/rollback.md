# PH09 Rollback Procedure

## Scope
Phase PH09 implements reliable transactional outbox and event lifecycle management:
- Outbox domain event schema contract (`contracts/events/outbox_domain_events.v1.json`)
- Idempotent outbox publisher & deduplication (`services/api/src/clara_api/db/outbox_publisher.py`)
- Outbox consumer retry and DLQ policy (`services/api/src/clara_api/glhs/outbox_retry_policy.py`)
- ML event subscription registry (`services/ml/src/clara_ml/event_subscriptions.py`)
- Web async job monitor with SSE and polling (`apps/web/lib/async-job-monitor.ts`)
- Mobile background job card widget (`apps/mobile/lib/widgets/background_job_card.dart`)
- Mobile pending job tracking integration tests (`services/api/tests/test_mobile_pending_job_tracking.py`)
- Outbox crash recovery simulation (`docs/security/QUEUE_FAILURE_AND_DLQ_AUDIT.md`, `scripts/ops/simulate_queue_recovery.py`)
- PHI-minimized event payload specification (`docs/research/PHI_MINIMIZED_EVENT_PAYLOAD_SECURITY.md`)
- Outbox operations runbook & PH09 quality gate (`docs/runbooks/outbox-operations-dlq-and-retention.md`, `scripts/ci/ph09_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 4c6621242a7dded10704a00ac298a87e5ecd54eb
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH09 --force
   ```
