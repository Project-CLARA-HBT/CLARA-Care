# Rollback Plan — PH12 A04 (Longitudinal Trajectory Baseline Recommendation Engine)

## Pre-Rollback State
- Base commit SHA: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- Branch: `phase/ph12-a04`

## Rollback Procedure
1. Revert modifications to configuration and module initialization:
   ```bash
   git checkout 36e5b95fac7e65712f0779de253d8ed18dc693d7 -- \
     services/ml/src/clara_ml/config.py \
     services/ml/src/clara_ml/lifemap/__init__.py
   ```
2. Remove newly added trajectory baseline module:
   ```bash
   rm -f services/ml/src/clara_ml/lifemap/longitudinal_trajectory.py
   ```
3. Remove evaluation test suite:
   ```bash
   rm -f evaluation/tests/test_longitudinal_trajectory_baseline.py
   ```
4. Remove phase deliverables:
   ```bash
   rm -rf artifacts/PH12/A04
   ```
5. Verification:
   ```bash
   git status
   git diff
   ```
