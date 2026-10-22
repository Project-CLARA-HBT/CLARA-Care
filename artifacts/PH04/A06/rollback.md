# Rollback Plan — PH04 A06 (Mobile Flutter: Tenant-Aware Mobile Navigation)

## Rollback Procedure
If tenant context propagation introduces regressions in mobile client behavior:

1. Restore modified Flutter source files:
   ```bash
   git -C /dev/shm/clara_worktrees/PH04_A06 checkout 7f458c915a59a75568e344b670d2f12ce9133a4e -- \
     apps/mobile/lib/core/api_client.dart \
     apps/mobile/lib/core/session_store.dart
   ```

2. Remove added test and artifacts:
   ```bash
   rm -f /dev/shm/clara_worktrees/PH04_A06/apps/mobile/test/api_client_tenant_organization_test.dart
   rm -rf /dev/shm/clara_worktrees/PH04_A06/artifacts/PH04/A06
   ```

3. Verification:
   ```bash
   flutter analyze --no-pub lib/core/api_client.dart lib/core/session_store.dart
   flutter test --no-pub test/session_store_test.dart
   ```
