# Test Report — PH49 A01 (API Contract + BFF: GLHS Provenance Redacted Read API)

## Environment
- Base commit SHA: `670a050a12e3c035ea6f316d3f2347963be699d7`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/control-plane/src/clara_control/api/router.py
```
Exit Code: `0`
Output: `Clean compilation, zero syntax errors.`

### 2. OpenAPI Schema Validation
```bash
python3 -c "import json; data=json.load(open('contracts/control-plane/control_v1_openapi.json')); assert '/control/v1/glhs/proposals' in data['paths']; print('GLHS endpoints verified in contract')"
```
Exit Code: `0`
Output: `GLHS endpoints verified in contract`

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A01 -p PH49 --files services/control-plane/src/clara_control/api/router.py contracts/control-plane/control_v1_openapi.json artifacts/PH49/A01/change_manifest.json artifacts/PH49/A01/test_report.md artifacts/PH49/A01/risk_register.md artifacts/PH49/A01/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A01, Phase: PH49)`
