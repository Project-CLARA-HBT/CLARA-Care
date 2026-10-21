# Rollback Plan — Subagent A05 (Web UX)

## Phase PH01 Scope
Subagent A05 operates within the following authorized path lane:
- `apps/web/app/`
- `apps/web/components/`
- `apps/web/lib/`
- `artifacts/PH01/A05/`

In PH01, Subagent A05's deliverables are strictly non-mutating audit, validation, and documentation artifacts located in `artifacts/PH01/A05/`:
- `artifacts/PH01/A05/change_manifest.json`
- `artifacts/PH01/A05/test_report.md`
- `artifacts/PH01/A05/risk_register.md`
- `artifacts/PH01/A05/rollback.md`
- `artifacts/PH01/A05/DEPENDENCY_REQUEST.md`

No production web or mobile code was modified in this lane.

## Rollback Procedures

### 1. Worktree Reversion
To revert the worktree back to the frozen baseline SHA `2aa9016a57b49b53f1a433d076e1028a6ec45f64`:
```bash
git checkout phase/ph01-a05
git reset --hard 2aa9016a57b49b53f1a433d076e1028a6ec45f64
git clean -fd
```

### 2. Upstream Reversion
If the branch commit is rejected during root integrator fan-in:
```bash
git branch -D phase/ph01-a05
```

### 3. State Invariants
- No database migrations were executed.
- No external packages or lockfiles were mutated.
- Safety invariants (RBAC, CSRF, Consent, FIDES, Emergency Fast-Path, Zero-CoT, PII sanitization) remain 100% intact and unaffected.
