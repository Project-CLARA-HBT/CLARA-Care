# Rollback Plan — PH05 A10 (Policy Language & Owner Approval)

## Rollback Procedure
1. Remove created runbook, audit report, and gate script:
   ```bash
   rm -f docs/runbooks/consent-policy-management-and-owner-approval.md
   rm -f docs/reports/ph05-consent-policy-and-authority-audit.md
   rm -f scripts/ci/ph05_quality_gate.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH05/A10
   ```
3. Verification:
   ```bash
   git status
   ```
