# Rollback Runbook: PH02_A08 Deterministic Red-Team Checker

- **Phase:** `PH02`
- **Subagent:** `A08` (Security + Privacy)
- **Branch:** `phase/ph02-a08`
- **Target Baseline Commit SHA:** `879dc5dcfcaae91b3626e28062043d934294478b`

---

## 1. Scope of Changes

Subagent A08 created only the following new files:
- `scripts/security/redteam_manifest_checker.py`
- `scripts/security/test_redteam_manifest_checker.py`
- `artifacts/PH02/A08/change_manifest.json`
- `artifacts/PH02/A08/test_report.md`
- `artifacts/PH02/A08/risk_register.md`
- `artifacts/PH02/A08/rollback.md`

No pre-existing repository files or database migrations were modified.

---

## 2. Reversion Steps

In the event that Subagent A08's deliverables must be rolled back:

1. **Delete created files:**
   ```bash
   git rm -f scripts/security/redteam_manifest_checker.py \
             scripts/security/test_redteam_manifest_checker.py \
             artifacts/PH02/A08/change_manifest.json \
             artifacts/PH02/A08/test_report.md \
             artifacts/PH02/A08/risk_register.md \
             artifacts/PH02/A08/rollback.md
   ```

2. **Hard reset to base commit:**
   ```bash
   git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
   ```

3. **Verify clean status:**
   ```bash
   git status
   # Expected: On branch phase/ph02-a08, nothing to commit, working tree clean
   ```
