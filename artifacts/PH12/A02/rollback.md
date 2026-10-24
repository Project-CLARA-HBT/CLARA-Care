# PH12-A02 Rollback Procedure

- **Phase:** PH12 (LifeMap longitudinal intelligence)
- **Agent:** A02 (Data model + migration)
- **Worktree:** `/dev/shm/clara_worktrees/PH12_A02`
- **Branch:** `phase/ph12-a02`
- **Base Commit:** `36e5b95fac7e65712f0779de253d8ed18dc693d7`

---

## 1. Migration Rollback (Database Schema)

If migration `20260908_0070` has been applied to a running database:

```bash
cd services/api
alembic downgrade 20260907_0069
```

This will execute the verified non-empty `downgrade()` in `services/api/alembic/versions/20260908_0070_lifemap_temporal_projection_cache.py`:
- Drop `lifemap_temporal_projection_caches` table
- Drop `lifemap_cache_invalidation_ledgers` table
- Drop `lifemap_state_versions` table

---

## 2. Source Code Rollback

To completely restore the worktree to the frozen baseline SHA `36e5b95fac7e65712f0779de253d8ed18dc693d7`:

```bash
# 1. Restore modified model registry
git checkout 36e5b95fac7e65712f0779de253d8ed18dc693d7 -- services/api/src/clara_api/db/models.py

# 2. Remove newly created DB modules and migrations
rm -f services/api/src/clara_api/db/lifemap_temporal_models.py
rm -f services/api/src/clara_api/db/lifemap_temporal_cache.py
rm -f services/api/src/clara_api/db/test_lifemap_temporal_cache.py
rm -f services/api/alembic/versions/20260908_0070_lifemap_temporal_projection_cache.py

# 3. Remove deliverables
rm -rf artifacts/PH12/A02
```

---

## 3. Clean State Verification

```bash
# Verify no untracked or modified files
git status

# Verify git diff against base is empty
git diff 36e5b95fac7e65712f0779de253d8ed18dc693d7
```

---

## 4. Git Branch Reset (If Committed)

```bash
git reset --hard 36e5b95fac7e65712f0779de253d8ed18dc693d7
```
