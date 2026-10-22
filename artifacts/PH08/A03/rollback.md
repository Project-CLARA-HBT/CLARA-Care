# Rollback Plan — PH08 A03 (Entity-Local OCC Locking Adapters)

## Rollback Procedure
1. Remove created adapter module:
   ```bash
   rm -f services/api/src/clara_api/glhs/occ_locking_adapters.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH08/A03
   ```
3. Verification:
   ```bash
   git status
   ```
