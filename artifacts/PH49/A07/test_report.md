# Test Report — PH49 A07 (Integration Tests: GLHS Adversarial Lineage & Snapshot Parity)

## Environment
- Base commit SHA: `670a050a12e3c035ea6f316d3f2347963be699d7`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. Integration Test Suite Execution
```bash
python3 -m unittest services/control-plane/tests/test_glhs_lineage_adversarial_reconciliation.py
```
Exit Code: `0`
Output:
```
Ran 3 tests in 0.000s
OK
```
Tests:
- `test_wrong_snapshot_id_rejected_fail_closed`: PASS
- `test_stale_or_revoked_consent_fails_admission`: PASS
- `test_attestation_receipt_parity`: PASS

### 2. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A07 -p PH49 --files services/control-plane/tests/test_glhs_lineage_adversarial_reconciliation.py artifacts/PH49/A07/change_manifest.json artifacts/PH49/A07/test_report.md artifacts/PH49/A07/risk_register.md artifacts/PH49/A07/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A07, Phase: PH49)`
