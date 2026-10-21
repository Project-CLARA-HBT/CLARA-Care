# Rollback Plan: PH03_A04 CSRF Bearer/Cookie Differential & Audit

## Scope
Rollback plan for changes introduced in Phase PH03 Subagent A04 (`evaluation/tests/test_csrf_bearer_cookie_differential.py` and deliverables under `artifacts/PH03/A04/`).

---

## 1. Runtime Abort / Emergency Deactivation

If CSRF enforcement produces unanticipated operational false positives or blocks legitimate user sessions in staging or production:
1. **Dynamic Bypass via Feature Flag:**
   Set the environment variable:
   ```bash
   export AUTH_CSRF_ENABLED=false
   ```
   Restart or reload the API gateway container. The `enforce_csrf_for_cookie_session` middleware will immediately short-circuit at `line 317` without executing cookie/header checks, restoring unrestricted cookie mutations.

---

## 2. Git Branch Reversion

To completely remove all changes introduced by subagent A04 and restore the baseline SHA:
```bash
# 1. Remove created test suite
git rm -f evaluation/tests/test_csrf_bearer_cookie_differential.py

# 2. Remove deliverables directory
git rm -rf artifacts/PH03/A04/

# 3. Reset branch to the pinned base SHA
git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3

# 4. Clean any untracked or residual files
git clean -fd
```

---

## 3. Verification Post-Rollback
Verify that the worktree is completely clean and matches the frozen HEAD:
```bash
git status
git rev-parse HEAD
# Output must equal: 3b1072b98350b978b83b7ecec5c35228415759a3
```
