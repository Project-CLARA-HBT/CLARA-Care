# Rollback Plan — PH13 A04 (Wearable Daily Aggregates Feature Extraction and Trend Analysis)

## Pre-Rollback State
- Base commit SHA: `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`
- Branch: `phase/ph13-a04`
- Worktree: `/dev/shm/clara_worktrees/PH13_A04`

## Rollback Procedure
1. Revert modifications to configuration and FastAPI application:
   ```bash
   git checkout bce92340e1f7a0709a96e9526e0682fa0fcb1e32 -- \
     services/ml/src/clara_ml/config.py \
     services/ml/src/clara_ml/main.py
   ```
2. Remove newly added wearables package:
   ```bash
   rm -rf services/ml/src/clara_ml/wearables
   ```
3. Remove evaluation test suite:
   ```bash
   rm -f evaluation/tests/test_wearable_aggregates_and_trends.py
   ```
4. Remove phase deliverables:
   ```bash
   rm -rf artifacts/PH13/A04
   ```
5. Verification:
   ```bash
   git status
   git diff
   ```
