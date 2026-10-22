# Rollback Plan — PH49 A07 (GLHS Adversarial Lineage & Snapshot Parity)

## Rollback Procedure
1. Remove created test file:
   ```bash
   rm -f services/control-plane/tests/test_glhs_lineage_adversarial_reconciliation.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH49/A07
   ```
3. Verification:
   ```bash
   git status
   ```
