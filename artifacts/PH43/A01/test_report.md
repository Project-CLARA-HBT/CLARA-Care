# Test Report — PH43 A01 (API Contract + BFF: RBAC/ABAC Permission Registry)

## Environment
- Base commit SHA: `89801b4823296c0065793e1140061e56cf574880`
- OS: Linux x86_64

## Verification Commands and Results

### 1. Contract Registry Validation
```bash
python3 -c "import json; data=json.load(open('contracts/control-plane/rbac_abac_permission_registry.v1.json')); assert len(data['platform_permissions']) >= 6; assert len(data['tenant_permissions']) >= 6; print('Permission registry verified')"
```
Exit Code: `0`
Output: `Permission registry verified`

### 2. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A01 -p PH43 --files contracts/control-plane/rbac_abac_permission_registry.v1.json artifacts/PH43/A01/change_manifest.json artifacts/PH43/A01/test_report.md artifacts/PH43/A01/risk_register.md artifacts/PH43/A01/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A01, Phase: PH43)`
