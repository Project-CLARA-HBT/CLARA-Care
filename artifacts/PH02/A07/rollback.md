# PH02 / A07 — Rollback Procedure: Merge Queue & Integration Worker

**Phase:** PH02 (Thiết lập tổ chức tác nhân và 10 worktree song song)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `879dc5dcfcaae91b3626e28062043d934294478b`
**Branch:** `phase/ph02-a07`

---

## 1. Scope of Changes

This package delivers:
1. `scripts/ops/merge_queue_worker.py`: Automated merge queue and subagent integration script.
2. `services/api/tests/test_merge_queue_worker.py`: 17 unit and integration tests.
3. `artifacts/PH02/A07/*`: Acceptance deliverables and manifests.

---

## 2. Reversion Steps

In the event of a defect or need to revert PH02 A07 changes on `phase/ph02-a07`:

### Fast Git Reversion:
```bash
# From worktree /dev/shm/clara_worktrees/PH02_A07:
git rm -f scripts/ops/merge_queue_worker.py services/api/tests/test_merge_queue_worker.py
git rm -rf artifacts/PH02/A07
git commit -m "revert(ph02-a07): revert merge queue worker implementation"
```

### Reset to Base SHA:
```bash
git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
```

---

## 3. Post-Rollback Verification

1. Verify working directory is clean:
   ```bash
   git status
   ```
2. Verify test suite passes without the worker module:
   ```bash
   pytest services/api/tests/test_sbom_and_dependency_integrity.py
   ```
