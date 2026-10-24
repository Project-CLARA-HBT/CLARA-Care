# PH12 Integration Demo — LifeMap Longitudinal Intelligence

## Scenario 1: Bi-Temporal Timeline Query with Scope Enforcement
1. Query longitudinal health events with valid-time windowing:
   ```bash
   curl -s -H "Authorization: Bearer $PATIENT_TOKEN" \
     "http://localhost:8000/api/v1/lifemap/timeline?limit=20&valid_time_from=2026-01-01T00:00:00Z" | jq .
   ```
2. Confirm items are sorted in reverse chronological order with immutable server timestamps and confirmed-only truth state.

## Scenario 2: Multi-Source Conflict Preservation Inspection
1. Inspect conflicting clinical assertions via Web/Admin UI:
   Navigate to `/lifemap/timeline` to inspect conflicting lab values or medication doses side-by-side with full provenance history and non-destructive dispute links.

## Scenario 3: Transitive Projection Invalidation
1. Correct an erroneous historical event:
   ```bash
   curl -s -X POST -H "Authorization: Bearer $PATIENT_TOKEN" \
     -H "Content-Type: application/json" \
     http://localhost:8000/api/v1/lifemap/events/evt-1234/correct \
     -d '{"corrected_value": "120/80", "reason": "Transcription typo corrected"}'
   ```
2. Verify downstream temporal projection cache entries are marked invalidated and recomputed on next access.
