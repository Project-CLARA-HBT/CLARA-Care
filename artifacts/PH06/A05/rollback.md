# Rollback Plan — PH06 A05 (Commit Kernel Dependency Wiring)

## Rollback Procedure
1. Remove created client files:
   ```bash
   rm -f apps/web/lib/commit-kernel-client.ts
   rm -f apps/web/lib/commit-kernel-client.test.ts
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH06/A05
   ```
3. Verification:
   ```bash
   git status
   ```
