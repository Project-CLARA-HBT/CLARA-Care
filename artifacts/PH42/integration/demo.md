# PH42 Demonstration Scenarios

## Scenario 1: OIDC Session Issuance, Device Binding & Step-Up
Execute the automated integration test suite validating that privileged administrative sessions require device binding and MFA TOTP verification:
```bash
PYTHONPATH="services/api/src:services/control-plane/src" python3 -m unittest services/control-plane/tests/test_oidc_mfa_step_up.py
```
**Expected Output:**
```text
Ran 4 tests in 0.042s
OK
```
This confirms that newly issued sessions start at STANDARD level, revoked sessions fail closed immediately upon introspection, and valid MFA codes elevate sessions to PRIVILEGED level.

## Scenario 2: Privileged Identity & MFA Quality Gate Execution
Execute the automated PH42 quality gate:
```bash
python3 scripts/ci/ph42_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH42 QUALITY GATE: PRIVILEGED IDENTITY OIDC MFA & STEP-UP
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] OIDC MFA & Step-Up Invariant Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH42 QUALITY GATE VERDICT: PASSED
```
This demonstrates complete privileged identity verification, device isolation, and session revocation enforcement.
