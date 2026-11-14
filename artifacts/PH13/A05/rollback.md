# PH13 A05 Rollback Procedure

**Phase:** PH13 — Connected Health và wearables
**Subagent:** A05 — Web UX
**Branch:** `phase/ph13-a05`
**Base Commit SHA:** `bce92340e190c62208a24aa3304f188080f6fd58`

---

## 1. Rollback Overview

A05 changes are strictly frontend UI components, library helpers, and client contracts in
Next.js (`apps/web`). There are no database migrations, schema alterations, or data deletions.
Reverting restores the prior integrations/measurements UX without affecting stored data.

---

## 2. Fast Rollback via Git

Run in the worktree root (`/dev/shm/clara_worktrees/PH13_A05`):

```bash
# Revert the A05 commit
git revert --no-edit HEAD

# Or reset impacted paths directly to the base SHA
git checkout bce92340e190c62208a24aa3304f188080f6fd58 -- \
  "apps/web/app/(consumer)/health" \
  "apps/web/app/(consumer)/you" \
  apps/web/components/health \
  apps/web/lib/api/v2-client.ts \
  apps/web/lib/wearable-sync.ts \
  apps/web/lib/wearable-sync.test.ts

# Remove newly added untracked-by-base files and artifacts
rm -f apps/web/components/health/wearable-reauth-modal.tsx \
      apps/web/components/health/wearable-stale-badge.tsx \
      apps/web/components/health/wearable-sync-alert-banner.tsx \
      apps/web/components/health/wearable-sync-alerts.test.tsx \
      apps/web/lib/wearable-sync.ts \
      apps/web/lib/wearable-sync.test.ts
rm -rf artifacts/PH13/A05

git status
```

> Note: `git revert` alone is preferred; the `checkout` variant is only for uncommitted-state
> recovery. Do not run both.

---

## 3. Post-Rollback Verification

```bash
cd apps/web
npx vitest run "app/(consumer)/you/you-pages.test.tsx" \
                 "app/(consumer)/health/health-pages.test.tsx"
npm run consumer-terminology:check
```

Expect both route suites to pass on the restored base commit and terminology to remain at
19 keys.

---

## 4. Runtime Behaviour Without Redeploy

Components are status-driven off `ConnectedHealthSourceDto.status`. If the backend emits
`status = "active"` or omits `error_message`, banners and stale badges clear automatically —
an effective soft-disable without rollback.
