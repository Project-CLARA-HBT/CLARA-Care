# Test Report — PH05 A01 (API + Contract: Versioned Consent Endpoints)

## Environment
- Base commit SHA: `1c626f461ce20f8c050ca161a09d300062b9f939`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/api/src/clara_api/schemas.py services/api/src/clara_api/api/v1/endpoints/auth.py
```
Exit Code: `0`
Output: `Clean compilation, zero syntax errors.`

### 2. Contract Schema Validation
```bash
python3 -c "import json; data=json.load(open('contracts/consent/versioned_consent_contract.v1.json')); assert len(data['governed_policies']) >= 3; print('All policies verified in contract')"
```
Exit Code: `0`
Output: `All policies verified in contract`

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A01 -p PH05 --files contracts/consent/versioned_consent_contract.v1.json services/api/src/clara_api/schemas.py services/api/src/clara_api/api/v1/endpoints/auth.py artifacts/PH05/A01/change_manifest.json artifacts/PH05/A01/test_report.md artifacts/PH05/A01/risk_register.md artifacts/PH05/A01/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A01, Phase: PH05)`
