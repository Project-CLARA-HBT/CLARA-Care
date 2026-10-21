# Rollback Plan — Subagent A05 (Web UX)

## Phase PH03 Scope
Subagent A05 operates within the following authorized path lanes:
- `apps/web/app/`
- `apps/web/components/`
- `apps/web/lib/`
- `artifacts/PH03/A05/`

In PH03, Subagent A05 implements OTP/login brute-force protection, audit of the web auth client, progressive delays, captcha/lockout behavior on failed attempts, and phase deliverables:
- `apps/web/app/auth/auth-pages.test.tsx`
- `apps/web/app/login/page.tsx`
- `apps/web/components/auth/auth-rate-limit-banner.test.tsx`
- `apps/web/components/auth/auth-rate-limit-banner.tsx`
- `apps/web/components/auth/auth-security-challenge.test.tsx`
- `apps/web/components/auth/auth-security-challenge.tsx`
- `apps/web/lib/auth-rate-limit.test.ts`
- `apps/web/lib/auth-rate-limit.ts`
- `apps/web/lib/http-client.ts`
- `apps/web/lib/i18n/catalog.ts`
- `artifacts/PH03/A05/change_manifest.json`
- `artifacts/PH03/A05/test_report.md`
- `artifacts/PH03/A05/risk_register.md`
- `artifacts/PH03/A05/rollback.md`

## Rollback Procedures

### 1. Worktree Reversion
To revert the worktree back to the frozen baseline SHA `3b1072b98350b978b83b7ecec5c35228415759a3`:
```bash
git checkout phase/ph03-a05
git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
git clean -fd
```

### 2. Upstream Reversion
If the branch commit is rejected during root integrator fan-in:
```bash
git branch -D phase/ph03-a05
```

### 3. State Invariants
- No database migrations, schemas, or backend data models were altered.
- No public API endpoints or contracts were modified.
- All core safety invariants (RBAC, CSRF, Consent Gate, Emergency Fast-Path, FIDES Critical Drug Gate, No-PII Telemetry) remain 100% intact and unaffected.
