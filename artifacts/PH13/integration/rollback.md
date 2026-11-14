# PH13 Integration Rollback Plan

## Rollback Trigger
Critical defects in wearable deduplication (data loss or silent overwrite), OAuth token handling, sync error signaling, or aggregation correctness.

## Step-by-Step Rollback
1. Runtime Kill-Switches:
   ```bash
   export LIFEMAP_WEARABLE_DEDUP_ENABLED=false
   export WEARABLE_AGGREGATES_ENABLED=false
   ```
2. Reset working branch to pre-PH13 base commit:
   ```bash
   git reset --hard bce92340e190c62208a24aa3304f188080f6fd58
   ```
3. Revert the OAuth secure-store migration if applied:
   ```bash
   (cd services/api && alembic downgrade 20260908_0070)
   ```
4. Verify clean status:
   ```bash
   git status
   ```
