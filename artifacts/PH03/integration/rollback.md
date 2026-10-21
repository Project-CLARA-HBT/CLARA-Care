# PH03 Rollback Procedure

## Scope
Phase PH03 hardens authentication and identity:
- Auth threat inventory & token contracts (`contracts/auth/`)
- User/Session/AuthToken models session invalidation (`services/api/src/clara_api/db/models.py`)
- Object-level profile scope IDOR protection (`services/api/src/clara_api/lifemap/profile_scope.py`)
- CSRF bearer/cookie differential protection (`evaluation/tests/test_csrf_bearer_cookie_differential.py`)
- Web OTP/login rate limit & security challenge (`apps/web/app/login/page.tsx`, `apps/web/lib/auth-rate-limit.ts`)
- Mobile secure password reset and biometric session store (`apps/mobile/lib/core/session_store.dart`)
- Web session UX states and silent refresh tests (`services/api/tests/test_auth_session_ux_states.py`)
- Mobile refresh rotation audit tool (`scripts/ops/audit_mobile_auth_session_security.py`)
- Security negative-test suite (`research/security_audit/`)
- Auth key rotation runbook and PH03 gate (`docs/runbooks/auth-hardening-and-key-rotation.md`, `scripts/ci/ph03_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH03 --force
   ```
