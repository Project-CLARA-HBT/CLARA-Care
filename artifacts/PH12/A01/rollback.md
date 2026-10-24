# Rollback Plan — PH12 A01 (LifeMap Timeline Event Query API)

## 1. Fast Rollback (Configuration Toggle)
To immediately deactivate the LifeMap Timeline Event Query V2 API without application redeployment or database rollbacks:
```bash
export LIFEMAP_TIMELINE_QUERY_V2_ENABLED=false
```
When `LIFEMAP_TIMELINE_QUERY_V2_ENABLED` is `false` (default), all requests to `/api/v1/lifemap/timeline/events`, `/api/v1/lifemap/events`, and `/api/v1/lifemap/events/{event_id}` fail closed immediately with HTTP 404 (`lifemap_timeline_query_v2_disabled`). Existing timeline endpoints remain functional on legacy behavior.

## 2. Full Code Rollback (Worktree Reversion)
To revert code changes back to the frozen baseline SHA `36e5b95fac7e65712f0779de253d8ed18dc693d7`:

```bash
cd /dev/shm/clara_worktrees/PH12_A01

# Revert modified files
git checkout 36e5b95fac7e65712f0779de253d8ed18dc693d7 -- \
  services/api/src/clara_api/api/v1/endpoints/lifemap.py \
  services/api/src/clara_api/schemas.py

# Remove new endpoints, contracts, and artifacts
rm -rf contracts/lifemap
rm -rf artifacts/PH12/A01
```

## 3. Post-Rollback Verification
Verify that the worktree is completely clean and matches the baseline commit:
```bash
git status --porcelain
git rev-parse HEAD
python3 -m compileall -q services/api/src/clara_api/api services/api/src/clara_api/schemas.py
```
Expected output: No untracked/modified files; commit matches `36e5b95fac7e65712f0779de253d8ed18dc693d7`.
