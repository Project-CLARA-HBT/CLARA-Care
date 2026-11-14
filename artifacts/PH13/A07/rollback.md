# PH13 / A07 — Rollback

**Branch:** `phase/ph13-a07`
**Base SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`
**Worktree:** `/dev/shm/clara_worktrees/PH13_A07`

## What this change adds

- `services/api/tests/test_connected_health_mobile_resync_integration.py` (new test suite, no production code changed)
- `artifacts/PH13/A07/` (manifest, test report, risk register, this rollback)

No source, schema, migration, or runtime configuration is modified. Rollback is purely additive removal.

## Rollback steps

1. Remove the new test suite:
   ```bash
   rm -f /dev/shm/clara_worktrees/PH13_A07/services/api/tests/test_connected_health_mobile_resync_integration.py
   ```
2. Remove the phase artifacts:
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH13_A07/artifacts/PH13/A07
   ```
3. If the work was committed, revert the commit(s) on the branch:
   ```bash
   git -C /dev/shm/clara_worktrees/PH13_A07 reset --hard bce92340e1f7a0709a96e9526e0682fa0fcb1e32
   ```
4. Confirm a clean tree at base:
   ```bash
   git -C /dev/shm/clara_worktrees/PH13_A07 status --short
   git -C /dev/shm/clara_worktrees/PH13_A07 rev-parse HEAD   # expected: bce92340...
   ```

## Verification after rollback

```bash
cd /dev/shm/clara_worktrees/PH13_A07/services/api
DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db \
  AUTH_AUTO_PROVISION_USERS=true \
  AUTH_BOOTSTRAP_ADMIN_ENABLED=true \
  uv run pytest -q tests/test_connected_health_control_plane.py
```

The pre-existing connected-health suites should still pass unchanged, confirming the removal was non-destructive.

## Blast radius

None outside the test lane and the agent artifact directory. Production behavior is unaffected because no `services/api/src`, `services/ml/src`, migration, or web/mobile files are touched.
