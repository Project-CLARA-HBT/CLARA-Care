# Test Report — PH11 A04 (Consent and Provenance Mapping for ML & Research Pipelines)

## Environment
- **Worktree**: `/dev/shm/clara_worktrees/PH11_A04`
- **Branch**: `phase/ph11-a04`
- **Base commit SHA**: `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
- **Python**: 3.12.3
- **Pytest**: 9.1.1
- **OS**: Linux x86_64

## Verification Commands and Execution Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/ml/src/clara_ml/config.py services/ml/src/clara_ml/fhir_consent_provenance.py evaluation/tests/test_fhir_consent_provenance.py
```
- **Exit Code**: `0`
- **Status**: `PASSED`
- **Process Output**: `Zero syntax or compilation errors.`

### 2. Unit and Concurrency Test Suite
```bash
pytest -v evaluation/tests/test_fhir_consent_provenance.py
```
- **Exit Code**: `0`
- **Status**: `PASSED`
- **Process Output**:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /dev/shm/clara_worktrees/PH11_A04
plugins: anyio-4.14.2, asyncio-1.4.0, hypothesis-6.167.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 25 items

evaluation/tests/test_fhir_consent_provenance.py::test_parse_valid_consent PASSED [  4%]
evaluation/tests/test_fhir_consent_provenance.py::test_parse_malformed_consent_fails PASSED [  8%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_allow_active_purpose PASSED [ 12%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_missing_fail_closed PASSED [ 16%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_patient_mismatch PASSED [ 20%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_not_active PASSED [ 24%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_expired PASSED [ 28%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_not_yet_valid PASSED [ 32%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_purpose_not_authorized PASSED [ 36%]
evaluation/tests/test_fhir_consent_provenance.py::test_consent_purpose_explicitly_denied PASSED [ 40%]
evaluation/tests/test_fhir_consent_provenance.py::test_statutory_cross_border_permitted PASSED [ 44%]
evaluation/tests/test_fhir_consent_provenance.py::test_statutory_cross_border_denied_when_missing PASSED [ 48%]
evaluation/tests/test_fhir_consent_provenance.py::test_research_pipeline_purpose_gate PASSED [ 52%]
evaluation/tests/test_fhir_consent_provenance.py::test_fhir_to_policy_epoch PASSED [ 56%]
evaluation/tests/test_fhir_consent_provenance.py::test_policy_epoch_to_fhir_consent PASSED [ 60%]
evaluation/tests/test_fhir_consent_provenance.py::test_model_provenance_to_fhir PASSED [ 64%]
evaluation/tests/test_fhir_consent_provenance.py::test_model_provenance_with_attested_dispatch PASSED [ 68%]
evaluation/tests/test_fhir_consent_provenance.py::test_scribe_provenance_to_fhir PASSED [ 72%]
evaluation/tests/test_fhir_consent_provenance.py::test_research_provenance_to_fhir PASSED [ 76%]
evaluation/tests/test_fhir_consent_provenance.py::test_provenance_lineage_no_downgrade PASSED [ 80%]
evaluation/tests/test_fhir_consent_provenance.py::test_provenance_lineage_downgrade_rejected PASSED [ 84%]
evaluation/tests/test_fhir_consent_provenance.py::test_provenance_pii_redaction PASSED [ 88%]
evaluation/tests/test_fhir_consent_provenance.py::test_gate_flag_disabled_passthrough PASSED [ 92%]
evaluation/tests/test_fhir_consent_provenance.py::test_gate_flag_enabled_enforces PASSED [ 96%]
evaluation/tests/test_fhir_consent_provenance.py::test_concurrent_consent_evaluation PASSED [100%]

============================== 25 passed in 0.66s ==============================
```

### 3. Agent Path ACL Conformance
```bash
python3 scripts/ci/check_agent_path_acl.py -a A04 -p PH11
```
- **Exit Code**: `0`
- **Status**: `PASSED`
- **Process Output**:
```
================================================================================
PATH ACL CHECKER — PASSED (Agent: A04, Phase: PH11)
================================================================================
Evaluated Files : 7
Allowed Lanes   : 8
  - services/ml/src/clara_ml/
  - evaluation/
  - services/ocr/
  - services/asr/
  - artifacts/PH11/A04/change_manifest.json
  - artifacts/PH11/A04/test_report.md
  - artifacts/PH11/A04/risk_register.md
  - artifacts/PH11/A04/

Result: All touched files conform strictly to the designated path lane.
```

## Coverage Summary
- **Allow & Deny Enforcement**: Fully verified on permitted, unconsented, and explicitly denied purposes.
- **Fail-Closed Guarantees**: Missing consent, patient mismatches, expired periods, and inactive states immediately reject inference.
- **Statutory Vietnamese Compliance**: Decree 13/2023/ND-CP cross-border processing gate and Circular 46/2018/TT-BYT requirements verified.
- **Lineage Anti-Downgrade**: Verified rejection of descendant proposal attestation level downgrades and snapshot digest mismatches.
- **Zero-PHI Sanitization**: Validated regex scrubbing of 12-digit CCCD, 9-digit CMND, Vietnamese phone numbers, emails, and patient ID hashing.
- **Concurrency**: 100 concurrent worker threads evaluated simultaneously without state corruption.
