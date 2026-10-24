# PH51 Integration Rollback Plan

## Rollback Trigger
Critical defects in background job dispatch, worker lease starvation, or unintended consent bypass.

## Step-by-Step Rollback
1. Reset working branch to pre-PH51 commit:
   ```bash
   git reset --hard 7d8840494cf8e30b6c70ea935574516604e4c275
   ```
2. Remove any lingering migration if deployed to database:
   ```bash
   (cd services/control-plane && alembic downgrade 20260908_0005)
   ```
3. Verify clean status:
   ```bash
   git status
   ```
