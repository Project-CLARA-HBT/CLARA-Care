# PH13 A01 — Rollback Plan

**Phase:** PH13 (Connected Health & Wearables)
**Agent:** A01 — API + Contract
**Branch:** `phase/ph13-a01`
**Base SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`

## Scope

Rollback removes the sync adapter protocol surface added by A01 without touching any other agent's lane.

## Steps

1. Revert the two modified source files to base SHA:
   ```bash
   git -C /dev/shm/clara_worktrees/PH13_A01 checkout bce92340e1f7a0709a96e9526e0682fa0fcb1e32 -- \
     services/api/src/clara_api/api/v1/endpoints/connected_health.py \
     services/api/src/clara_api/schemas.py
   ```
2. Remove the new contract directory (untracked at base):
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH13_A01/contracts/connected_health
   ```
3. Remove the phase artifacts:
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH13_A01/artifacts/PH13/A01
   ```
4. Verify a clean tree against base:
   ```bash
   git -C /dev/shm/clara_worktrees/PH13_A01 status --porcelain
   git -C /dev/shm/clara_worktrees/PH13_A01 diff --stat bce92340e1f7a0709a96e9526e0682fa0fcb1e32
   ```
5. Re-run lane check; it should report zero touched files:
   ```bash
   python3 /home/clue/Documents/CLARA-Care/scripts/ci/check_agent_path_acl.py -a A01 -p PH13
   ```

## Post-Rollback Verification

- `python3 -m compileall -q services/api/src/clara_api/api services/api/src/clara_api/schemas.py` exits 0.
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_connected_health_control_plane.py -q` still passes (pre-existing connector plane intact).
- No references to `SyncAdapter*` schemas remain in `services/api/src`.

## Data / Migration Impact

None. A01 adds no database migration and no persisted schema change; `ConnectorSyncCursor` reuse is read/write of an existing table introduced before PH13. Rolling back code leaves stored cursors valid but unused.

## Non-Goals

- Does not revert any work by A02–A10.
- Does not alter existing `/connectors/{id}/imports`, `/sync`, `/pause`, `/resume`, or `/imported-data` semantics beyond restoring them to base behavior.
