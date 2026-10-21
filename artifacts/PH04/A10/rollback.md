# Rollback Plan: PH04 Subagent A10 Deliverables

**Phase:** PH04 — Multi-tenant Organizations & Workspaces  
**Subagent:** Subagent A10 — Adversarial Audit + Integration Proposals  
**Worktree:** `/dev/shm/clara_worktrees/PH04_A10`  
**Branch:** `phase/ph04-a10`  
**Base SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`  
**Status:** READY  

---

## 1. Scope & Isolation

Subagent A10 deliverables consist strictly of additive operational documentation, audit reports, quality gate scripts, and phase artifacts within assigned path lanes:
- `docs/runbooks/tenant-onboarding-and-organization-management.md`
- `docs/reports/ph04-tenant-isolation-and-lane-audit.md`
- `scripts/ci/ph04_quality_gate.py`
- `artifacts/PH04/A10/change_manifest.json`
- `artifacts/PH04/A10/test_report.md`
- `artifacts/PH04/A10/risk_register.md`
- `artifacts/PH04/A10/rollback.md`

No shared core source code, existing database migration files, or production endpoints were destructively altered by A10.

---

## 2. Worktree Level Rollback

To immediately revert the worktree to the baseline commit SHA without residual state:

```bash
cd /dev/shm/clara_worktrees/PH04_A10
git reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
git clean -ffdx
```

---

## 3. Operational Rollback for Tenant Onboarding Procedures

If an onboarding or migration procedure fails during tenant provisioning:

1. **Mark Tenant as Quarantined:**
   ```bash
   # Halt incoming requests to newly provisioned tenant
   UPDATE organizations SET status = 'quarantined' WHERE tenant_id = :target_tenant_id;
   ```
2. **Purge Partial Tenant Resources:**
   - Remove partially seeded default workspaces and folder records.
   - Delete pending invitation tokens issued to the tenant's initial admin.
   - Flush tenant-scoped Redis keys (`redis-cli --scan --pattern "tenant:${TENANT_ID}:*" | xargs -r redis-cli del`).
3. **Verify Host Tenant Isolation:**
   - Execute smoke tests on existing organizations to confirm zero side effects on concurrent tenants.
