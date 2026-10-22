# Test Report — PH41 A08 (Security / Negative Tests: Threat Model & Network Segmentation)

## Environment
- Base commit SHA: `f161b49db7c3c54117b8841da3675f92fe19543e`
- Markdown Linter: Enabled
- OS: Linux x86_64

## Verification Commands and Results

### 1. Document Integrity Check
```bash
python3 -c "from pathlib import Path; doc = Path('docs/security/CONTROL_PLANE_NETWORK_AND_SSO_THREAT_MODEL.md').read_text(); assert '__Host-' in doc; assert 'DATABASE_CONTROL_URL' in doc; print('Threat model verified')"
```
Exit Code: `0`
Output: `Threat model verified`

### 2. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A08 -p PH41 --files docs/security/CONTROL_PLANE_NETWORK_AND_SSO_THREAT_MODEL.md artifacts/PH41/A08/change_manifest.json artifacts/PH41/A08/test_report.md artifacts/PH41/A08/risk_register.md artifacts/PH41/A08/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A08, Phase: PH41)`
