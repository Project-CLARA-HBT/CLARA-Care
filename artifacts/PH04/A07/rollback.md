# PH04 / A07 — Rollback Procedure: Mobile Org Switch & Deep-Link Test Suite

**Phase:** PH04 (Multi-tenant organizations và workspaces)
**Subagent:** A07 (Tests + CI)
**Role:** Tests + CI
**Frozen HEAD SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`
**Branch:** `phase/ph04-a07`
**Date:** October 21, 2026

---

## 1. Scope of Delivered Changes

Subagent A07 delivered strictly additive test suites and documentation residing within its assigned path lane:
1. `services/api/tests/test_mobile_org_switching_and_deep_links.py`: 21 automated backend unit and integration tests covering deep link intake, capability tokens, workspace isolation, context cache headers, and presentation mode separation.
2. `apps/web/e2e/org-switch-deep-link.spec.ts`: Playwright E2E specification covering deep link unauthenticated redirection (`?next=`), safe capability preview, context switcher, and expired link fail-closed handling.
3. `artifacts/PH04/A07/*`: Acceptance deliverables and manifests (`change_manifest.json`, `test_report.md`, `risk_register.md`, `rollback.md`).

No existing backend application endpoints, database models, or shared production code were modified.

---

## 2. Reversion Steps

In the event of a need to revert PH04 A07 changes on branch `phase/ph04-a07`:

### Procedural Git Reversion:
```bash
# Run from worktree root /dev/shm/clara_worktrees/PH04_A07
git rm -f services/api/tests/test_mobile_org_switching_and_deep_links.py
git rm -f apps/web/e2e/org-switch-deep-link.spec.ts
git rm -rf artifacts/PH04/A07
git commit -m "revert(ph04-a07): rollback mobile org switch and deep-link test suite"
```

### Complete Reset to Frozen Base SHA:
```bash
git reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
```

---

## 3. Post-Rollback Verification

1. Verify git status is clean:
   ```bash
   git status
   ```
2. Run baseline organization and workspace test suite to verify zero side-effects:
   ```bash
   CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test_a07.db" python3 -m pytest -q services/api/tests/test_workspace_endpoints.py services/api/tests/test_family_circle_v2.py
   ```
