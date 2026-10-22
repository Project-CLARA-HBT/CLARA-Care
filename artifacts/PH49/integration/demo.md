# PH49 Demonstration Scenarios

## Scenario 1: GLHS Proposal Provenance Inspection & Human Review
Execute the adversarial lineage reconciliation integration test suite validating that proposals bound to wrong snapshots or revoked consents fail admission:
```bash
PYTHONPATH="services/control-plane/src" python3 -m unittest services/control-plane/tests/test_glhs_lineage_adversarial_reconciliation.py
```
**Expected Output:**
```text
Ran 3 tests in 0.000s
OK
```
This confirms that wrong snapshot IDs are rejected, revoked consent fails admission, and unverified provider receipts default to base application envelope levels.

## Scenario 2: GLHS Operations & Immutable Lineage Quality Gate Execution
Execute the automated PH49 quality gate:
```bash
python3 scripts/ci/ph49_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH49 QUALITY GATE: GLHS OPERATIONS & IMMUTABLE LINEAGE AUDIT
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] GLHS Lineage & Provenance Invariant Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH49 QUALITY GATE VERDICT: PASSED
```
This demonstrates complete provenance tracking and non-repudiation across GLHS proposal lineages.
