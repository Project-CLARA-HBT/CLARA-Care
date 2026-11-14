# PH13 / A07 — Test Report

**Role:** Tests + CI
**Task:** mobile permission/resync flows
**Suite:** `services/api/tests/test_connected_health_mobile_resync_integration.py`
**Base SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`
**Branch:** `phase/ph13-a07`

## Environment

```
DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db
AUTH_AUTO_PROVISION_USERS=true
AUTH_BOOTSTRAP_ADMIN_ENABLED=true
python: CPython 3.12.3 (.venv via uv)
```

## Command

```bash
cd services/api
DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db \
  AUTH_AUTO_PROVISION_USERS=true \
  AUTH_BOOTSTRAP_ADMIN_ENABLED=true \
  uv run pytest -q tests/test_connected_health_mobile_resync_integration.py
```

## Result

```
..............                                                           [100%]
=============================== warnings summary ===============================
../../../../../../home/clue/.local/lib/python3.12/site-packages/fastapi/testclient.py:1
  /home/clue/.local/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_connected_health_mobile_resync_integration.py: 12 warnings
  /home/clue/.local/lib/python3.12/site-packages/sqlalchemy/engine/default.py:952: DeprecationWarning: The default datetime adapter is deprecated as of Python 3.12; see the sqlite3 documentation for suggested replacement recipes
    cursor.execute(statement, parameters)

tests/test_connected_health_mobile_resync_integration.py::test_wearable_import_rejects_scope_or_provider_mismatch
  /dev/shm/clara_worktrees/PH13_A07/services/api/src/clara_api/api/v1/endpoints/connected_health.py:124: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    return import_batch(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 14 warnings in 493.37s (0:08:13)
```

**Exit code:** `0`

All warnings are third-party deprecations (Starlette/TestClient, SQLAlchemy sqlite datetime adapter) and one pre-existing FastAPI status-constant deprecation in the base endpoint code. No test failures, no errors, no skips.

## Coverage Map

| # | Test | Behavior asserted |
|---|------|-------------------|
| 1 | `test_wearable_import_batch_multi_type_ingestion_and_aggregates` | Multi-type ingestion (steps + heart_rate), observation rows, version_no=1, sync cursor advance, daily aggregate projection. |
| 2 | `test_wearable_import_batch_updates_create_versions` | Re-ingest with new raw hash increments `version_no` to 2 and snapshots v1 in `WearableObservationVersion`. |
| 3 | `test_wearable_import_batch_tombstone_soft_deletes_and_recomputes_aggregate` | Tombstone sets `is_active=False`, bumps version, stamps `deleted_at`, and removes the aggregate. |
| 4 | `test_wearable_import_rejects_scope_or_provider_mismatch` | 403 on connector/profile scope mismatch; 422 on provider mismatch. |
| 5 | `test_consent_revocation_blocks_import_and_requires_reauthorization` | Disconnect yields `disconnected`; subsequent sync 409 "must be reauthorized"; import 409 "not available for imports". |
| 6 | `test_permission_unconsented_data_type_is_blocked` | Heart-rate record against steps-only consent returns 403 "unconsented". |
| 7 | `test_delete_imported_data_cascades_and_invalidates_aggregates` | `DELETE /{connector_id}/imported-data` removes observations, invalidates aggregates, writes `connector.imported_data_deleted` audit event. |
| 8 | `test_resync_idempotency_exact_replay` | Exact batch replay returns `idempotent_replay=True`, same `batch_id`, single `ConnectorImportBatch` row. |
| 9 | `test_resync_idempotency_key_reuse_conflict` | Same key + altered payload returns 409 "already used for another payload". |
| 10 | `test_sync_request_emits_transactional_outbox_event` | `POST /{connector_id}/sync` returns `device_import_required`, emits pending `LifeMapOutboxEvent` (`connector_account`, `connector.sync_requested`) and audit row attributed to actor. |
| 11 | `test_csrf_rejects_cookie_authenticated_device_creation_without_csrf` | Cookie-auth mutation without CSRF pair returns 403 "CSRF validation failed". |
| 12 | `test_csrf_rejects_cookie_authenticated_sync_with_mismatched_csrf` | Mismatched CSRF cookie/header returns 403. |
| 13 | `test_csrf_allows_bearer_authenticated_connector_mutation` | Bearer-only mutation bypasses CSRF and creates a `connected` connector (201). |
| 14 | `test_csrf_allows_cookie_authenticated_mutation_with_matching_csrf` | Matching CSRF cookie/header cookie-auth mutation succeeds (201). |

## Notes

- Tests exercise the **real FastAPI app** (`clara_api.main.app`) with `TestClient` and the real SQLAlchemy session/DB, matching the existing `services/api/tests/` pattern. No global mocks or fake subsystems.
- CSRF cases are guarded by `settings.auth_csrf_enabled`; when the flag is disabled those three cases return early rather than assert behavior that cannot exist. The Bearer-bypass case always runs.
- All asserted endpoints, error strings, tables and events exist in the base commit (`bce92340`); no A01/A03 forward dependencies were required.
