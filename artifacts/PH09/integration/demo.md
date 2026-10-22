# PH09 Demonstration Scenarios

## Scenario 1: Outbox Worker Crash & Lease Reclamation
Execute the outbox queue crash simulation proving that stalled events are automatically reclaimed upon worker failure:
```bash
python3 scripts/ops/simulate_queue_recovery.py
```
**Expected Output:**
```json
{
  "status": "recovery_verified",
  "initial_event_claimed": true,
  "reclaimed_after_crash": true,
  "attempts_incremented": true
}
```
This confirms that worker crashes do not cause permanent event loss or stalled pipelines.

## Scenario 2: Transactional Outbox Quality Gate Execution
Execute the automated PH09 quality gate:
```bash
python3 scripts/ci/ph09_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH09 QUALITY GATE: RELIABLE TRANSACTIONAL OUTBOX & EVENT LIFECYCLE
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] Outbox Event Lifecycle & Retry Policy Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH09 QUALITY GATE VERDICT: PASSED
```
This demonstrates reliable at-least-once transactional event dispatch without PII leakage.
