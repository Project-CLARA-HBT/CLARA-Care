# PH04 Demonstration Scenarios

## Scenario 1: Multi-Tenant Workspace & Organization Isolation (Happy Path)
Execute the multi-tenant isolation verification validating that data records, idempotency keys, and query adapters are partitioned hermetically by tenant ID:
```bash
python3 scripts/ci/ph04_quality_gate.py --verify-isolation
```
**Expected Output:**
```text
[PASS] All 4 multi-tenant isolation unit tests PASSED cleanly
```
This confirms that cross-tenant queries return uniform HTTP 404 and that idempotency scopes prevent cross-tenant key collision.

## Scenario 2: Mobile Organization Context & Header Propagation (Positive Path)
Execute the mobile API client organization header propagation suite:
```bash
flutter test --no-pub apps/mobile/test/api_client_tenant_organization_test.dart
```
**Expected Output:**
```text
00:02 +5: All tests passed!
```
This confirms that mobile REST, streaming, and multipart requests attach `X-CLARA-Organization-Id` correctly and that `PersistentSessionStore` persists and isolates tenant context.
