# PH13 Integration Demo — Connected Health và Wearables

## Scenario 1: Wearable Data Ingestion with Deduplication
1. Import a wearable batch (Health Connect / Huawei Health / Fitbit):
   ```bash
   curl -s -X POST -H "Authorization: Bearer $PATIENT_TOKEN" \
     -H "Content-Type: application/json" \
     http://localhost:8000/api/v1/connected-health/connectors/1/imports \
     -d @wearable_batch.json | jq .
   ```
2. Replaying the identical batch yields `duplicate_skipped` — deterministic SHA-256 dedup keys per provider/record/metric/window.
3. A newer revision from the same device supersedes the old record (`superseded`); disagreement across providers is preserved side-by-side (`conflict_preserved`), never overwritten.

## Scenario 2: Daily Aggregates & Trend Detection
1. Request deterministic daily aggregates (steps, resting heart rate, sleep):
   ```bash
   curl -s -X POST -H "X-ML-Internal-Key: $ML_KEY" \
     http://localhost:8010/v1/wearables/aggregates/daily -d @daily_batch.json | jq .
   ```
2. Request a trend: robust Theil-Sen slope with a source-switch critic and non-diagnostic disclaimer:
   ```bash
   curl -s -X POST -H "X-ML-Internal-Key: $ML_KEY" \
     http://localhost:8010/v1/wearables/trends/analyze -d @trend_request.json | jq .
   ```

## Scenario 3: Sync Error / Stale Data UX and Reauthorization
1. Open the consumer Integrations page (`/you/integrations`) — stale connectors surface a badge and an alert banner; a revoked token surfaces the reauthorization modal.
2. On mobile, the Connected Health screen lists providers with pause/resume, sync-now, last-sync time, and a full data-deletion affordance.
