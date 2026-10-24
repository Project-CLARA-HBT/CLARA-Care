# Rollback Plan — PH11 A10 (Vendor EHR Sandbox Guide & Adversarial Interoperability Audit)

## Rollback Procedure

1. Remove adversarial audit report, integration guide runbook, gate manifest, and deliverables:
   ```bash
   rm -f docs/reports/ph11-adversarial-interoperability-audit.md
   rm -f docs/runbooks/vendor-ehr-sandbox-integration-guide.md
   rm -f artifacts/phase-gates/PH11_gate_manifest.json
   rm -rf artifacts/PH11/A10
   git checkout -- scripts/ci/check_agent_path_acl.py
   ```

2. Confirm Clean Worktree State:
   ```bash
   git status
   ```

3. Emergency Feature Flag Kill-Switch (Production / Staging):
   Ensure interoperability endpoints remain disabled:
   ```bash
   export LIFEMAP_FHIR_EXPORT_ENABLED=false
   export LIFEMAP_FHIR_IMPORT_ENABLED=false
   ```
