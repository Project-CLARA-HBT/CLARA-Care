# Rollback Plan — PH51 A06 (Retry Approval & Redacted Failure Inspector Components)

## Rollback Procedure
1. Remove components and deliverables:
   ```bash
   rm -f apps/admin/components/retry_approval_modal.tsx
   rm -f apps/admin/components/redacted_failure_inspector.tsx
   rm -rf artifacts/PH51/A06
   ```
2. Verification:
   ```bash
   git status
   ```
