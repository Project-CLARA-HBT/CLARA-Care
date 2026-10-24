# PH11 Integration Rollback Plan

## Rollback Trigger
Critical defects in FHIR serialization, patient identification leakage, or statutory consent bypass in interoperability projections.

## Step-by-Step Rollback
1. Runtime Kill-Switch:
   ```bash
   export FHIR_CAPABILITY_STATEMENT_ENABLED=false
   export LIFEMAP_FHIR_EXPORT_ENABLED=false
   export LIFEMAP_FHIR_IMPORT_ENABLED=false
   ```
2. Reset working branch to pre-PH11 base commit:
   ```bash
   git reset --hard 85cef4b2d9a0e926ca684e9eeeba5e588ab11600
   ```
3. Revert database migration if applied:
   ```bash
   (cd services/api && alembic downgrade 20260906_0068)
   ```
4. Verify clean status:
   ```bash
   git status
   ```
