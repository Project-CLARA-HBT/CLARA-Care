# Rollback Plan — PH40 A02 (Control-Plane DB Models & OpenAPI Inventory)

## Rollback Procedure
1. Remove created control-plane database package:
   ```bash
   rm -rf services/control-plane/src/clara_control/db
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH40/A02
   ```
3. Verification:
   ```bash
   git status
   ```
