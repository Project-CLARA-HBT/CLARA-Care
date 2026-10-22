# Rollback Plan — PH08 A01 (Clinical Dependency Schema Registry)

## Rollback Procedure
1. Remove created contract:
   ```bash
   rm -f contracts/glhs/clinical_dependency_registry.v1.json
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH08/A01
   ```
3. Verification:
   ```bash
   git status
   ```
