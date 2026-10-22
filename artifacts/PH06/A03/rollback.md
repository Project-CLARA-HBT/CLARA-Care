# Rollback Plan — PH06 A03 (THSS Identity & Digest Check)

## Rollback Procedure
1. Revert admission module modifications:
   ```bash
   git -C /dev/shm/clara_worktrees/PH06_A03 checkout 2370329965f32a7e7df48473e6a2b842ae37580b -- services/api/src/clara_api/glhs/admission.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH06/A03
   ```
3. Verification:
   ```bash
   git status
   ```
