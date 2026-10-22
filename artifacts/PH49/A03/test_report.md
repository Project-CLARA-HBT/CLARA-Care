# Test Report — PH49 A03 (Domain Service: GLHS Reconciliation & Deny Reasons)

## Environment
- Base commit SHA: `670a050a12e3c035ea6f316d3f2347963be699d7`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/control-plane/src/clara_control/domain/glhs_reconciliation.py
```
Exit Code: `0`
Output: `Clean compilation, zero syntax errors.`

### 2. Reconciliation Record Execution Unit Check
```bash
python3 -c "
from clara_control.domain.glhs_reconciliation import GlhsReconciliationService
rec = GlhsReconciliationService.record_decision(
    proposal_id='prop-1',
    decision='REJECTED',
    reviewer_email='pharmacist@hospital.vn',
    deny_code='STALE_DEPENDENCY_VERSION',
    notes='Medication list was updated by attending physician',
)
assert rec.decision == 'REJECTED'
assert rec.deny_code == 'STALE_DEPENDENCY_VERSION'
assert 'Observed entity partition' in GlhsReconciliationService.DENY_CODE_DESCRIPTIONS[rec.deny_code]
print('Reconciliation domain service verified')
"
```
Exit Code: `0`
Output: `Reconciliation domain service verified`

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A03 -p PH49 --files services/control-plane/src/clara_control/domain/glhs_reconciliation.py artifacts/PH49/A03/change_manifest.json artifacts/PH49/A03/test_report.md artifacts/PH49/A03/risk_register.md artifacts/PH49/A03/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A03, Phase: PH49)`
