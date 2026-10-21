# Rollback Plan — Subagent A05 (Web UX)

## Phase PH02 Scope
Subagent A05 operates within the following authorized path lane:
- `apps/web/app/`
- `apps/web/components/`
- `apps/web/lib/`
- `scripts/ci/`
- `artifacts/PH02/A05/`

In PH02, Subagent A05 implements the path ACL verification script and phase deliverables:
- `scripts/ci/check_agent_path_acl.py`
- `artifacts/PH02/A05/change_manifest.json`
- `artifacts/PH02/A05/test_report.md`
- `artifacts/PH02/A05/risk_register.md`
- `artifacts/PH02/A05/rollback.md`

## Rollback Procedures

### 1. Worktree Reversion
To revert the worktree back to the frozen baseline SHA `879dc5dcfcaae91b3626e28062043d934294478b`:
```bash
git checkout phase/ph02-a05
git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
git clean -fd
```

### 2. Upstream Reversion
If the branch commit is rejected during root integrator fan-in:
```bash
git branch -D phase/ph02-a05
```

### 3. State Invariants
- No database migrations or schema alterations were introduced.
- No production application APIs or web front-end routes were altered.
- All safety invariants (RBAC, CSRF, Consent, FIDES, Emergency Fast-Path, Zero-CoT, PII sanitization) remain 100% intact and unaffected.
