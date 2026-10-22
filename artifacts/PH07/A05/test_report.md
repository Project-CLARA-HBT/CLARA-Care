# Test Report — PH07 A05 (Web UX: Provider Identity & Model-Registry Binding)

## Environment
- Base commit SHA: `e8533cb029a1470ce2d1bc027a421b47664871c5`
- Node: 20
- OS: Linux x86_64

## Verification Commands and Results

### 1. Model Registry Unit Test Suite
```bash
npm run test -- lib/model-registry.test.ts
```
Exit Code: `0`
Output:
```
 ✓ lib/model-registry.test.ts (3 tests) 5ms
 Test Files  1 passed (1)
      Tests  3 passed (3)
```
Tests:
- `resolves approved DeepSeek models with appropriate attestation requirements`: PASS
- `validates approved model for specific clinical task family`: PASS
- `rejects unauthorized third-party model identifiers`: PASS

### 2. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A05 -p PH07 --files apps/web/lib/model-registry.ts apps/web/lib/model-registry.test.ts artifacts/PH07/A05/change_manifest.json artifacts/PH07/A05/test_report.md artifacts/PH07/A05/risk_register.md artifacts/PH07/A05/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A05, Phase: PH07)`
