# Rollback Plan — PH12 A10 (LifeMap Product Tutorial & Adversarial Longitudinal Audit)

## Rollback Procedure

1. Remove created runbook, audit report, gate script, phase gate manifest, and deliverables:
   ```bash
   rm -f docs/runbooks/lifemap-product-tutorial-and-acceptance.md
   rm -f docs/reports/ph12-adversarial-longitudinal-audit.md
   rm -f scripts/ci/ph12_quality_gate.py
   rm -f artifacts/phase-gates/PH12_gate_manifest.json
   rm -rf artifacts/PH12/A10
   ```

2. Confirm Clean Worktree State:
   ```bash
   git status
   ```

3. Emergency Feature Flag Kill-Switch (Production / Staging):
   If longitudinal intelligence features exhibit anomalies or require immediate suspension:
   ```bash
   # Disable longitudinal intelligence endpoints and background workers
   export LIFEMAP_LONGITUDINAL_ENABLED=false
   export LIFEMAP_CAPTURE_WORKER_ENABLED=false
   export LIFEMAP_EVIDENCE_MONITOR_ENABLED=false
   export LIFEMAP_NBQ_LLM_ENRICHMENT_ENABLED=false
   ```
   Restart service:
   ```bash
   systemctl restart clara-api
   ```
