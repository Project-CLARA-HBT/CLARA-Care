# PH12 Integration Rollback Plan

## Rollback Trigger
Critical defects in temporal query boundary enforcement, cross-profile document bleed in retrieval index, or projection cache corruption.

## Step-by-Step Rollback
1. Runtime Kill-Switch:
   ```bash
   export LIFEMAP_LONGITUDINAL_ENABLED=false
   export LIFEMAP_NBQ_LLM_ENRICHMENT_ENABLED=false
   export LIFEMAP_EVIDENCE_MONITOR_ENABLED=false
   ```
2. Reset working branch to pre-PH12 base commit:
   ```bash
   git reset --hard 36e5b95facf155985012354e6005bb7097c36d0b
   ```
3. Revert database migration if applied:
   ```bash
   (cd services/api && alembic downgrade 20260907_0069)
   ```
4. Verify clean status:
   ```bash
   git status
   ```
