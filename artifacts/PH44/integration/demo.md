# PH44 Demonstration Scenarios

## Scenario 1: Tenant Organization Lifecycle & Signed Invitation Verification
Execute the tenant suspension and invitation replay test suite:
```bash
PYTHONPATH="services/control-plane/src" python3 -m unittest services/control-plane/tests/test_tenant_suspension_and_invite_replay.py
```
**Expected Output:**
```text
Ran 4 tests in 0.000s
OK
```
This confirms that newly onboarded clinics can issue signed staff invitations, tampered and expired invitations are rejected, and suspended organizations fail closed.

## Scenario 2: Organization Lifecycle Quality Gate Execution
Execute the automated PH44 quality gate:
```bash
python3 scripts/ci/ph44_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH44 QUALITY GATE: ORGANIZATION LIFECYCLE, ONBOARDING & FEDERATION
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] Organization Lifecycle & Suspension Invariant Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH44 QUALITY GATE VERDICT: PASSED
```
This demonstrates complete B2B tenant onboarding, suspension governance, and workspace federation.
