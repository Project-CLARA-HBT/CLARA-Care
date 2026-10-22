# PH10 Demonstration Scenarios

## Scenario 1: Bi-Temporal Knowledge Replay & Point-In-Time State Reconstruction
Execute the bi-temporal replay engine unit verification demonstrating that historical patient state can be reconstructed as of any point in time without retrospective knowledge leakage:
```bash
python3 -c "
import datetime
from clara_ml.bitemporal_replay import BiTemporalClinicalFact, BiTemporalReplayEngine

t0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
t1 = datetime.datetime(2026, 2, 1, tzinfo=datetime.UTC)
t2 = datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC)

engine = BiTemporalReplayEngine()
engine.add_fact(BiTemporalClinicalFact(
    fact_id='f1',
    fact_type='medication',
    payload={'drug': 'aspirin'},
    valid_from=t0,
    valid_to=t2,
    transaction_recorded_at=t1,
))

# As of t0 transaction time, fact was not recorded yet
assert len(engine.replay_as_of(as_of_valid_time=t0, as_of_transaction_time=t0)) == 0

# As of t1 transaction time and t0 valid time, fact is active
assert len(engine.replay_as_of(as_of_valid_time=t0, as_of_transaction_time=t1)) == 1

print('Bi-temporal replay verified successfully')
"
```
**Expected Output:**
```text
Bi-temporal replay verified successfully
```
This confirms that clinical knowledge evaluates strictly against what was recorded at transaction time.

## Scenario 2: Health Data Normalization Quality Gate Execution
Execute the automated PH10 quality gate:
```bash
python3 scripts/ci/ph10_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH10 QUALITY GATE: HEALTH DATA NORMALIZATION & MASTER RECORD
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] Medical Vocabulary & Normalization Invariant Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH10 QUALITY GATE VERDICT: PASSED
```
This demonstrates complete medical vocabulary mapping, conflict preservation, and physiological normalization.
