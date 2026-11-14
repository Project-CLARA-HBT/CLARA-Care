# Rollback Plan — PH13 / A03 (Wearable Dedup and Multi-Source Version Mapping)

## Rollback Triggers
- Any caller wired to the engine observes unexpected `conflict_preserved` or
  `superseded` outcomes that change a user-visible health trend.
- Determinism regression: identical batches produce different `map_versions`
  results across processes or versions.
- Path ACL or lint/type gates begin failing after downstream integration.

## Fast Feature Flag Kill-Switch (preferred)
The engine is guarded by `lifemap_wearable_dedup_enabled` (default `False`).
To disable instantly with no deploy:

```bash
export LIFEMAP_WEARABLE_DEDUP_ENABLED=false
```

When unset or `false`, both `WearableDeduplicationEngine.evaluate` and
`.map_versions` raise `WearableDedupDisabledError` before any decision is made.
No records, counters, or persisted state are modified by this module in the
first place — it is a pure decision layer — so flag-off is a zero-data-change
rollback.

## Full Code Rollback

Revert everything to the base commit
`bce92340e1f7a0709a96e9526e0682fa0fcb1e32`
(`bce92340e190c62208a24aa3304f188080f6fd58` in this worktree):

### Step 1: Revert the Settings change
```bash
git checkout bce92340e190c62208a24aa3304f188080f6fd58 -- \
  services/api/src/clara_api/core/config.py
```

### Step 2: Remove the new domain module and its tests
```bash
rm -f services/api/src/clara_api/lifemap/wearable_dedup.py
rm -f services/api/src/clara_api/lifemap/test_wearable_dedup.py
```

### Step 3: Remove the artifacts directory
```bash
rm -rf artifacts/PH13/A03
```

### Step 4: Verify
```bash
cd services/api
python3 -m compileall -q src/clara_api/lifemap src/clara_api/core
PYTHONPATH=src python3 -m pytest src/clara_api/lifemap/ -q
```

## Commit-Level Rollback

This agent's work was committed as a single commit on `phase/ph13-a03`:

```bash
git revert d04de72b6f9b09aefbe7c32ef85bca92b97bbf8d
```

If the branch has not been shared:

```bash
git reset --hard bce92340e190c62208a24aa3304f188080f6fd58
```

## Post-Rollback Checks
- `LIFEMAP_WEARABLE_DEDUP_ENABLED` absent or `false`.
- `services/api/src/clara_api/lifemap/wearable_dedup.py` absent.
- `python3 /home/clue/Documents/CLARA-Care/scripts/ci/check_agent_path_acl.py -a A03 -p PH13` still passes.
- Existing connected-health ingestion (`connected_health/ingestion.py`) is
  untouched by this change set and continues to run unmodified.
