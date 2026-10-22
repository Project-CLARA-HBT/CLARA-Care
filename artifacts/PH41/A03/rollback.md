# Rollback Plan — PH41 A03 (Service-Token Gateway & Tenant Governor)

## Rollback Procedure
1. Remove created domain modules:
   ```bash
   rm -f services/control-plane/src/clara_control/domain/service_token_gateway.py
   rm -f services/control-plane/src/clara_control/domain/tenant_governor.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH41/A03
   ```
3. Verification:
   ```bash
   git status
   ```
