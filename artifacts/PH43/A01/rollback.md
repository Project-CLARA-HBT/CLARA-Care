# Rollback Plan — PH43 A01 (RBAC/ABAC Permission Registry)

## Rollback Procedure
1. Remove created contract:
   ```bash
   rm -f contracts/control-plane/rbac_abac_permission_registry.v1.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH43/A01
   ```
3. Verification:
   ```bash
   git status
   ```
