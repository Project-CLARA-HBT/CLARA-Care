# Rollback — PH13 A06 (Connected Health và wearables — Mobile)

## Preconditions

- Worktree: `/dev/shm/clara_worktrees/PH13_A06`
- Branch: `phase/ph13-a06`
- Base SHA: `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`
- Deliverable commit: the commit created by A06 that contains the two modified source files plus the new widget test and `artifacts/PH13/A06/`.

## Rollback Steps

1. Revert the deliverable commit (preferred, keeps history auditable):

```bash
git -C /dev/shm/clara_worktrees/PH13_A06 revert --no-edit <A06_COMMIT_SHA>
```

2. Or restore the touched source files to the base SHA and remove the new test file:

```bash
git -C /dev/shm/clara_worktrees/PH13_A06 checkout bce92340e1f7a0709a96e9526e0682fa0fcb1e32 -- \
  apps/mobile/lib/core/api_client.dart \
  apps/mobile/lib/experience/connected_health/connected_health_screen.dart
rm -f /dev/shm/clara_worktrees/PH13_A06/apps/mobile/test/connected_health_screen_test.dart
```

3. Remove generated artifact bundle (optional):

```bash
rm -rf /dev/shm/clara_worktrees/PH13_A06/artifacts/PH13/A06
```

4. Confirm clean state:

```bash
git -C /dev/shm/clara_worktrees/PH13_A06 status --porcelain
```

Expected residual: none of the A06 files remain modified/untracked (build artifacts such as `apps/mobile/.flutter-plugins` are ignored and may legitimately reappear after a rebuild).

## Verification After Rollback

```bash
cd /dev/shm/clara_worktrees/PH13_A06/apps/mobile
dart analyze lib/core/api_client.dart lib/experience/connected_health/connected_health_screen.dart
```

The screen should compile against the base implementation (no `createDeviceConnector`), and `test/connected_health_screen_test.dart` must be absent.

## Notes

- No database migrations, no server-side state, and no feature flags are involved; rollback is purely client code plus artifact files.
- The generated `apps/mobile/.flutter-plugins` file is never committed and requires no rollback action.
