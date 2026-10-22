# Rollback Plan — PH42 A06 (Session Inventory & Revocation UX)

## Rollback Procedure
1. Remove created component:
   ```bash
   rm -f apps/admin/components/session_inventory.tsx
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH42/A06
   ```
3. Verification:
   ```bash
   git status
   ```
