# Rollback Plan: PH03 Subagent A10 Deliverables

**Phase:** PH03 — Hardening Auth & Identity
**Subagent:** Subagent A10 — Adversarial Audit + Integration Proposals
**Worktree:** `/dev/shm/clara_worktrees/PH03_A10`
**Branch:** `phase/ph03-a10`
**Base SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
**Status:** READY

---

## 1. Scope & Isolation

Subagent A10 deliverables are strictly additive documentation, quality gate scripts, and audit artifacts within the assigned path lane:
- `docs/runbooks/auth-hardening-and-key-rotation.md`
- `docs/reports/ph03-auth-hardening-and-lane-audit.md`
- `scripts/ci/ph03_quality_gate.py`
- `artifacts/PH03/A10/change_manifest.json`
- `artifacts/PH03/A10/test_report.md`
- `artifacts/PH03/A10/risk_register.md`
- `artifacts/PH03/A10/rollback.md`

No shared core source files, database schemas, or API runtime endpoints were modified directly by A10.

---

## 2. Worktree Level Rollback

To immediately revert the worktree to the baseline commit SHA:

```bash
cd /dev/shm/clara_worktrees/PH03_A10
git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
git clean -ffdx
```

---

## 3. Operational Rollback for Key Rotation Procedure

If a key rotation operation fails during execution in staging or production:

1. **Restore Previous Key as Active:**
   ```bash
   export JWT_SECRET_KEY="$JWT_SECRET_KEY_PREVIOUS"
   export JWT_SECRET_KEY_PREVIOUS=""
   ```
2. **Redeploy API Services:**
   Perform a rolling restart of the API cluster. All previously issued tokens will continue to validate without error.
3. **Verify Baseline Token Functionality:**
   Execute a smoke test asserting that existing user sessions and new tokens validate under the original key.
