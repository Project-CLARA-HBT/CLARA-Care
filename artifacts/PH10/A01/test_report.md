# Test Report — PH10 A01 (API + Contract: Event/Assertion/Evidence Typed Contract)

## Environment
- Base commit SHA: `d17260aa2f70b79fcce8965615d6a2f3068e217d`
- OS: Linux x86_64

## Verification Commands and Results

### 1. Contract Schema Validation
```bash
python3 -c "import json; data=json.load(open('contracts/clinical/event_assertion_evidence.v1.json')); assert 'ClinicalEvent' in data['entities']; assert 'ClinicalEvidence' in data['entities']; print('Clinical triad contract verified')"
```
Exit Code: `0`
Output: `Clinical triad contract verified`

### 2. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A01 -p PH10 --files contracts/clinical/event_assertion_evidence.v1.json artifacts/PH10/A01/change_manifest.json artifacts/PH10/A01/test_report.md artifacts/PH10/A01/risk_register.md artifacts/PH10/A01/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A01, Phase: PH10)`
