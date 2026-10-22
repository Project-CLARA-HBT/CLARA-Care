# Test Report — PH06 A08 (Security: Stale-Write & Downgrade Threat Model)

## Environment
- Base commit SHA: `2370329965f32a7e7df48473e6a2b842ae37580b`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. Lineage Audit Script Execution
```bash
python3 scripts/ops/audit_thss_lineage.py
```
Exit Code: `0`
Output:
```json
{
  "status": "audited",
  "max_lineage_depth": 4,
  "acyclic_invariant_enforced": true,
  "anti_downgrade_enforced": true,
  "occ_freshness_revalidation": "PHASE_3_UNDER_LOCKS"
}
```

### 2. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A08 -p PH06 --files docs/security/GLHS_STALE_WRITE_AND_DOWNGRADE_THREAT_MODEL.md scripts/ops/audit_thss_lineage.py artifacts/PH06/A08/change_manifest.json artifacts/PH06/A08/test_report.md artifacts/PH06/A08/risk_register.md artifacts/PH06/A08/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A08, Phase: PH06)`
