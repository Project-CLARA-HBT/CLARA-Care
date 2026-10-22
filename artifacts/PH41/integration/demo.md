# PH41 Demonstration Scenarios

## Scenario 1: Isolated Control Plane Gateway Readiness Probe
Execute the control plane integration test suite validating that the separate control plane reports isolated network status and governance routes:
```bash
PYTHONPATH="services/api/src:services/control-plane/src" python3 -m unittest services/control-plane/tests/test_forbidden_cross_origin_admin.py
```
**Expected Output:**
```text
Ran 3 tests in 0.017s
OK
```
This confirms that the control plane runs on an isolated plane, exposes governance routes summary, and fails closed on unknown actions.

## Scenario 2: Separate Control Plane Quality Gate Execution
Execute the automated PH41 quality gate:
```bash
python3 scripts/ci/ph41_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH41 QUALITY GATE: SEPARATE ADMIN CONTROL-PLANE ARCHITECTURE
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] Control-Plane Isolation & Security Test Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH41 QUALITY GATE VERDICT: PASSED
```
This demonstrates complete architectural separation between control and data planes.
