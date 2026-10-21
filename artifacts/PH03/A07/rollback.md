# PH03 / A07 — Rollback Procedure: Web Session UX & Auth Test Audit

**Phase:** PH03 (Hardening auth và identity)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
**Branch:** `phase/ph03-a07`

---

## 1. Scope of Changes

This package delivers:
1. `services/api/tests/test_auth_session_ux_states.py`: 14 automated backend unit and integration tests auditing token expiration, silent refresh lifecycle, CSRF cookie rotation, secret key rotation grace periods, and credential isolation.
2. `apps/web/e2e/session-ux.spec.ts`: Playwright E2E test suite for web session handling, silent refresh recovery, expired session redirection with destination preservation (`?next=...`), public route immunity, and clean logout.
3. `artifacts/PH03/A07/*`: Acceptance deliverables and manifests (`change_manifest.json`, `test_report.md`, `risk_register.md`, `rollback.md`).

All changes in this package are additive test cases and documentation residing strictly within the authorized path lane.

---

## 2. Reversion Steps

In the event of a need to revert PH03 A07 deliverables on branch `phase/ph03-a07`:

### Fast Git Reversion:
```bash
# From worktree /dev/shm/clara_worktrees/PH03_A07:
git rm -f services/api/tests/test_auth_session_ux_states.py
git rm -f apps/web/e2e/session-ux.spec.ts
git rm -rf artifacts/PH03/A07
git commit -m "revert(ph03-a07): rollback web session UX tests and deliverables"
```

### Complete Reset to Base SHA:
```bash
git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
```

---

## 3. Post-Rollback Verification

1. Verify working directory is clean:
   ```bash
   git status
   ```
2. Verify existing authentication test suite remains functional:
   ```bash
   CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test_auth.db" python3 -m pytest -q services/api/tests/test_auth_*.py
   ```
