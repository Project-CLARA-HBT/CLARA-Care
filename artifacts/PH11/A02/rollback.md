# Rollback Runbook: PH11 Subagent A02 (FHIR Patient/Observation Import)

## Summary
This document provides step-by-step procedures to revert the database schema and application code introduced by subagent `A02` in Phase `PH11`.

---

## 1. Rollback Triggers
Rollback should be executed if any of the following occur:
- Downstream deployment failures during Alembic database migration upgrade.
- Post-merge integration regressions in services importing from `clara_api.db.fhir_models` or `clara_api.db.fhir_import`.
- Unacceptable performance overhead during FHIR bundle ingestion.
- Integrity or authorization violations detected during fan-in security scans.

---

## 2. Database Schema Rollback

To revert the database schema changes:
```bash
# In services/api directory
cd services/api

# Revert migration 20260907_0069 back to 20260906_0068
alembic downgrade 20260906_0068
```

### Verification of Schema Rollback
Verify that tables and indexes have been dropped cleanly:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('fhir_import_batches', 'fhir_patients', 'fhir_observations');
-- Expected result: 0 rows returned
```

---

## 3. Code & Worktree Reversion

To revert code modifications on the subagent branch:
```bash
# Return to the frozen base commit
git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
    services/api/src/clara_api/db/models.py

# Remove newly created files
rm -f services/api/src/clara_api/db/fhir_models.py
rm -f services/api/src/clara_api/db/fhir_import.py
rm -f services/api/src/clara_api/db/test_fhir_import.py
rm -f services/api/alembic/versions/20260907_0069_fhir_patient_observation_import.py
rm -rf artifacts/PH11/A02/
```

### Git Branch Reset Alternative
If discarding the entire branch commit:
```bash
git reset --hard 85cef4b2d9a0e926ca684e9eeeba5e588ab11600
git clean -fd
```

---

## 4. Post-Rollback Validation
1. Verify migrations check passes on previous head:
   ```bash
   python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions
   ```
2. Verify Python compilation:
   ```bash
   python3 -m compileall services/api/src/clara_api/db/ services/api/alembic/versions/
   ```
3. Run existing test suite:
   ```bash
   (cd services/api && pytest -q tests/test_auth_and_rbac.py)
   ```
