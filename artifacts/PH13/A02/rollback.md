# PH13 A02 Rollback Runbook: OAuth Secure Store & Lease Locking

## Overview

This document details the step-by-step procedures to cleanly roll back the changes introduced in Phase PH13 Agent A02 (`OAuth callback/refresh secure store and lease locking`).

## Rollback Scope

- Database schema migration: `services/api/alembic/versions/20260909_0071_oauth_secure_store_and_lease.py`
- Persistence models: `services/api/src/clara_api/db/oauth_secure_models.py`
- Service operations: `services/api/src/clara_api/db/oauth_secure_store.py`
- Test suite: `services/api/src/clara_api/db/test_oauth_secure_store.py`
- Model export updates: `services/api/src/clara_api/db/models.py`

## Rollback Procedures

### Step 1: Database Migration Rollback

Execute Alembic downgrade to the previous revision (`20260908_0070`):

```bash
cd services/api
alembic downgrade 20260908_0070
```

Verify current revision is `20260908_0070`:

```bash
alembic current
```

This will safely drop the following tables and their associated indexes in proper foreign key order:
1. `connector_lease_locks`
2. `connector_refresh_token_rotations`
3. `connector_oauth_tokens`

### Step 2: Codebase Rollback

Revert code files back to the base SHA `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`:

```bash
# Revert models.py
git checkout bce92340e1f7a0709a96e9526e0682fa0fcb1e32 -- services/api/src/clara_api/db/models.py

# Remove added modules and migration
rm -f services/api/src/clara_api/db/oauth_secure_models.py
rm -f services/api/src/clara_api/db/oauth_secure_store.py
rm -f services/api/src/clara_api/db/test_oauth_secure_store.py
rm -f services/api/alembic/versions/20260909_0071_oauth_secure_store_and_lease.py
rm -rf artifacts/PH13/A02
```

### Step 3: Verification Post-Rollback

Confirm the working directory is clean and migration tree is intact:

```bash
python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions --strict
python3 -m compileall services/api/src/clara_api/db/ services/api/alembic/versions/
pytest services/api/src/clara_api/db/test_lifemap_temporal_cache.py
```
