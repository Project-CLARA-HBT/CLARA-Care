# Rollback Plan — PH44 A07 (Suspended Org & Invite Replay)

## Rollback Procedure
1. Remove created test file:
   ```bash
   rm -f services/control-plane/tests/test_tenant_suspension_and_invite_replay.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH44/A07
   ```
3. Verification:
   ```bash
   git status
   ```
