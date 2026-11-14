# PH13 A05 Test Report: Wearable Sync Errors, Stale-Data Alerts, and Reauthorization Prompts

**Phase:** PH13 — Connected Health và wearables
**Subagent:** A05 — Web UX
**Branch:** `phase/ph13-a05`
**Base SHA:** `bce92340e190c62208a24aa3304f188080f6fd58`
**Worktree:** `/dev/shm/clara_worktrees/PH13_A05`
**Status:** PASSED

---

## 1. Executive Summary

Subagent A05 implemented the frontend Web UX for wearable sync errors, stale-data warnings,
and reauthorization prompts in Next.js (`apps/web`). Patients and clinicians are alerted when
biometric telemetry is degraded, stale (> 24h, critical > 72h), or halted by expired vendor
OAuth credentials. All changes remain within the designated path lane:
`apps/web/app/`, `apps/web/components/`, `apps/web/lib/`, `artifacts/PH13/A05/`.

---

## 2. Test Execution

### Command 1 — combined wearable/health/you suites

```bash
cd apps/web && npx vitest run \
  lib/wearable-sync.test.ts \
  components/health/wearable-sync-alerts.test.tsx \
  "app/(consumer)/health/health-pages.test.tsx" \
  "app/(consumer)/you/you-pages.test.tsx"
```

Real output (tail):

```
 RUN  v2.1.9 /dev/shm/clara_worktrees/PH13_A05/apps/web

 ✓ lib/wearable-sync.test.ts (22 tests) 16ms
 ✓ components/health/wearable-sync-alerts.test.tsx (10 tests) 247ms
 ✓ app/(consumer)/health/health-pages.test.tsx (6 tests) 448ms
 ✓ app/(consumer)/you/you-pages.test.tsx (17 tests) 1677ms
   ✓ You & Privacy Route Pages > You Overview Page (/you — Spec v5 Section 6.74 Account & Preferences Hub) > renders Identity & Profile card, all 8 categorized vertical list rows, emergency alerts, and quick QR modal 599ms

 Test Files  4 passed (4)
      Tests  55 passed (55)
   Start at  18:30:11
   Duration  104.54s (transform 6.65s, setup 70.79s, collect 64.79s, tests 2.39s, environment 243.56s, prepare 615ms)
```

`EXIT_CODE=0`

> The stderr `connect ECONNREFUSED 127.0.0.1:3000` lines are expected jsdom warnings from
> negative-path tests that intentionally exercise API-failure states; all assertions passed.

### Command 2 — API v2 client suite

```bash
cd apps/web && npx vitest run lib/api/v2-client.test.ts
```

Real output (tail):

```
 RUN  v2.1.9 /dev/shm/clara_worktrees/PH13_A05/apps/web

 ✓ lib/api/v2-client.test.ts (24 tests) 89ms

 Test Files  1 passed (1)
      Tests  24 passed (24)
```

`EXIT_CODE=0`

### Command 3 — consumer terminology contract

```bash
cd apps/web && npm run consumer-terminology:check
```

Real output (tail):

```
consumer terminology projection check passed: 19 keys, 2026-07-30.v1.
consumer terminology contract passed: 19 keys, 2026-07-30.v1.
```

`EXIT_CODE=0`

---

## 3. Coverage Summary

| Suite | Tests | Status |
|---|---|---|
| `lib/wearable-sync.test.ts` | 22 | PASSED |
| `components/health/wearable-sync-alerts.test.tsx` | 10 | PASSED |
| `app/(consumer)/health/health-pages.test.tsx` | 6 | PASSED |
| `app/(consumer)/you/you-pages.test.tsx` | 17 | PASSED |
| `lib/api/v2-client.test.ts` | 24 | PASSED |
| `consumer-terminology:check` | 19 keys | PASSED |

**Total tests executed: 79 passed, 0 failed, 0 skipped.**

---

## 4. Positive and Negative Paths Covered

1. **Positive paths**
   - Freshly synced wearable (< 24h): "Active & Connected" / "Đang kết nối", tone `ok`, no banner.
   - Successful manual sync: updates status, shows confirmation, triggers refetch.
   - Successful reauthorization: opens `WearableReauthModal`, presents read-only scope guarantee,
     completes handshake, updates source status.
2. **Negative paths**
   - OAuth credential expiration: flagged `reauth_required`, danger banner with
     "Cần cấp lại quyền" / "Reauthorize Grant", launches modal.
   - Reauthorization API failure (e.g. 502): inline error in modal with retry, no crash.
   - Stale data (> 24h): warning banner + `WearableStaleBadge` on affected vital cards.
   - Critically stale (> 72h): badge tone escalates to danger.
   - Disconnected source: excluded from fleet alerts to reduce noise.

---

## 5. Clinical Safety & Architectural Invariants

- **Stale-data safety:** fresh-sync absence is surfaced prominently to prevent false clinical
  reassurance on outdated vitals.
- **Privacy:** reauthorization modal states read-only scope, no raw password/token stored in
  browser storage, instant revocation available.
- **No PII telemetry:** error strings contain only vendor codes and non-identifying text.
- **Additive contract:** `reauthorizeIntegrationSource` extends `v2Client` without breaking
  existing route contracts; response handled via HttpOnly session cookies (no browser bearer).
