# Rollback Plan — PH11 A05 (Web UX: Encounter/Documents Export)

## Overview
This document specifies the step-by-step procedures to revert all code changes made by subagent `A05` during phase `PH11`.

---

## Rollback Procedure

### 1. Revert Modified Files
Revert `apps/web/lib/scribe.ts` and `apps/web/app/visits/[visitId]/page.tsx` back to the frozen base commit:
```bash
git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
  apps/web/lib/scribe.ts \
  apps/web/app/visits/[visitId]/page.tsx
```

### 2. Remove Created Export Components and Routes
Remove the newly introduced modules in `apps/web`:
```bash
rm -rf apps/web/app/api/export
rm -rf apps/web/components/export
rm -f apps/web/lib/fhir-encounter-export.ts
rm -f apps/web/lib/fhir-encounter-export.test.ts
```

### 3. Remove Artifacts
Remove deliverables for Phase PH11 A05:
```bash
rm -rf artifacts/PH11/A05
```

### 4. Post-Rollback Verification
Confirm that the working tree is clean and matches the base commit:
```bash
git status --porcelain
git diff 85cef4b2d9a0e926ca684e9eeeba5e588ab11600
```
