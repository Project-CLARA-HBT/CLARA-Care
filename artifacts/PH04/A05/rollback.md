# Rollback Plan — Subagent A05 (Web UX)

## Phase PH04 Scope
Subagent A05 operates within the following authorized path lane:
- `apps/web/app/`
- `apps/web/components/`
- `apps/web/lib/`
- `artifacts/PH04/A05/`

### Modified Production Files:
- `apps/web/lib/http-client.ts` (added `X-CLARA-Organization-Id` header injection)
- `apps/web/lib/api/v2-client.ts` (added `organizationId` option and header injection)
- `apps/web/components/clinical/patient-roster.tsx` (integrated `OrganizationSwitcher` and `OrganizationLinkBadge`)
- `apps/web/app/clinical/clinical-pages.test.tsx` (added assertions for organization link dossier in patient inspector)

### New Production & Test Files:
- `apps/web/lib/organization-context.ts`
- `apps/web/lib/organization-context.test.ts`
- `apps/web/lib/organization-api.ts`
- `apps/web/lib/organization-api.test.ts`
- `apps/web/components/organization/organization-provider.tsx`
- `apps/web/components/organization/organization-provider.test.tsx`
- `apps/web/components/organization/organization-switcher.tsx`
- `apps/web/components/organization/organization-switcher.test.tsx`
- `apps/web/components/organization/organization-link-badge.tsx`
- `apps/web/components/organization/organization-link-badge.test.tsx`

### Deliverable Artifacts:
- `artifacts/PH04/A05/change_manifest.json`
- `artifacts/PH04/A05/test_report.md`
- `artifacts/PH04/A05/risk_register.md`
- `artifacts/PH04/A05/rollback.md`

---

## Rollback Procedures

### 1. Worktree Reversion
To cleanly revert the worktree back to the frozen baseline SHA `7f458c915a59a75568e344b670d2f12ce9133a4e`:
```bash
git -C /dev/shm/clara_worktrees/PH04_A05 checkout 7f458c915a59a75568e344b670d2f12ce9133a4e -- \
  apps/web/app/clinical/clinical-pages.test.tsx \
  apps/web/components/clinical/patient-roster.tsx \
  apps/web/lib/api/v2-client.ts \
  apps/web/lib/http-client.ts

rm -rf /dev/shm/clara_worktrees/PH04_A05/artifacts/PH04/A05
rm -rf /dev/shm/clara_worktrees/PH04_A05/apps/web/components/organization
rm -f /dev/shm/clara_worktrees/PH04_A05/apps/web/lib/organization-context.ts
rm -f /dev/shm/clara_worktrees/PH04_A05/apps/web/lib/organization-context.test.ts
rm -f /dev/shm/clara_worktrees/PH04_A05/apps/web/lib/organization-api.ts
rm -f /dev/shm/clara_worktrees/PH04_A05/apps/web/lib/organization-api.test.ts

git -C /dev/shm/clara_worktrees/PH04_A05 reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
git -C /dev/shm/clara_worktrees/PH04_A05 clean -fd
```

### 2. Client-Side Cache Invalidation
If reverting in a live client environment, ensure client-side storage keys are cleared:
```javascript
localStorage.removeItem("clara_active_org_id");
Object.keys(localStorage).forEach(k => {
  if (k.startsWith("clara_org_cache:") || k.startsWith("clara_tenant_cache:")) {
    localStorage.removeItem(k);
  }
});
```

### 3. State Invariants
- No database migrations were executed or modified by Subagent A05.
- No package dependencies or lockfiles were added or modified.
- Core safety invariants (RBAC, CSRF, Consent, Emergency Fast-Path, FIDES, No-PII telemetry) remain 100% intact.
