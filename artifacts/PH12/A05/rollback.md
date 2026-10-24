# PH12-A05 Rollback Procedure & Operational Runbook

**Phase:** PH12 — LifeMap longitudinal intelligence  
**Agent:** A05 (Web UX)  
**Worktree:** `/dev/shm/clara_worktrees/PH12_A05`  
**Branch:** `phase/ph12-a05`  
**Base Commit SHA:** `36e5b95facf155985012354e6005bb7097c36d0b`  
**Date:** October 24, 2026  

---

## 1. Scope of Changes

Subagent A05 delivered the **Conflict Provenance UI** for LifeMap longitudinal intelligence. All modifications are strictly confined within A05's authorized write lanes:
- `apps/web/app/lifemap/timeline/page.tsx`
- `apps/web/app/lifemap/timeline/page.test.tsx`
- `apps/web/components/lifemap/conflict-provenance-inspector.tsx`
- `apps/web/components/lifemap/conflict-provenance-inspector.test.tsx`
- `apps/web/components/lifemap/longitudinal-conflict-timeline.tsx`
- `apps/web/components/lifemap/longitudinal-conflict-timeline.test.tsx`
- `apps/web/components/lifemap/multi-source-contradiction-banner.tsx`
- `apps/web/lib/lifemap-conflict-provenance.ts`
- `apps/web/lib/lifemap-conflict-provenance.test.ts`
- `artifacts/PH12/A05/change_manifest.json`
- `artifacts/PH12/A05/test_report.md`
- `artifacts/PH12/A05/risk_register.md`
- `artifacts/PH12/A05/rollback.md`

No backend API routes, database schemas, or Alembic migrations were modified.

---

## 2. Zero-Downtime Feature Flag Kill-Switch

If any client-side rendering issue, latency, or UX confusion is encountered in production, the conflict provenance capability can be immediately disabled without requiring a redeployment or service restart:

```bash
# In Next.js environment configuration (.env.production / runtime env)
export NEXT_PUBLIC_LIFEMAP_CONFLICT_PROVENANCE_ENABLED=false
```

### Operational Effect:
1. `isLifeMapConflictProvenanceEnabled()` returns `false`.
2. `JourneyTimelinePage` bypasses all review finding scans and multi-source contradiction queries.
3. The page renders standard timeline cards without contradiction alert ribbons or inspector modals.
4. Core timeline filtering, bitemporal sorting, and existing dispute flows continue operating seamlessly.

---

## 3. Git Worktree Rollback Procedure

### Step 1: Revert Modified Files
To restore modified files back to the base commit:
```bash
cd /dev/shm/clara_worktrees/PH12_A05

git checkout 36e5b95facf155985012354e6005bb7097c36d0b -- \
  apps/web/app/lifemap/timeline/page.tsx \
  apps/web/app/lifemap/timeline/page.test.tsx
```

### Step 2: Remove Newly Created Components and Libraries
To delete untracked components and library files created for this task:
```bash
rm -f \
  apps/web/components/lifemap/conflict-provenance-inspector.tsx \
  apps/web/components/lifemap/conflict-provenance-inspector.test.tsx \
  apps/web/components/lifemap/longitudinal-conflict-timeline.tsx \
  apps/web/components/lifemap/longitudinal-conflict-timeline.test.tsx \
  apps/web/components/lifemap/multi-source-contradiction-banner.tsx \
  apps/web/lib/lifemap-conflict-provenance.ts \
  apps/web/lib/lifemap-conflict-provenance.test.ts
```

### Step 3: Remove Generated Deliverables
```bash
rm -rf artifacts/PH12/A05
```

### Step 4: Complete Clean Reset (Alternative)
To completely reset the branch to the base commit:
```bash
git checkout phase/ph12-a05
git reset --hard 36e5b95facf155985012354e6005bb7097c36d0b
git clean -fd
```

---

## 4. Post-Rollback Verification

Execute the following commands to confirm clean rollback:
```bash
# 1. Verify working directory is clean
git status --porcelain
# Expected: empty output

# 2. Run web tests to confirm base integrity
cd apps/web && npx vitest run app/lifemap/timeline/page.test.tsx
# Expected: All base timeline tests pass
```
