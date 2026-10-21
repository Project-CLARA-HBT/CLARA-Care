# PH03 / A07 — Test Report: Web Session UX States & Auth Test Audit

**Phase:** PH03 (Hardening auth và identity)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
**Branch:** `phase/ph03-a07`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Scope & Objective

Subagent A07 is tasked with:
1. **Auditing the auth test suite** across `services/api/tests/test_auth_*.py` and hardening tests to evaluate coverage of token expiry, refresh token rotation, session invalidation, and credential boundaries.
2. **Auditing and augmenting web E2E session handling**:
   - Expired session redirections (`/login?next=...`)
   - Silent refresh recovery upon transient 401s
   - Retention of public routes without forced authentication bounces
   - Explicit user logout session purging
3. **Delivering comprehensive automated tests** across the designated path lane (`services/api/tests/`, `apps/web/e2e/`, `artifacts/PH03/A07/`).

---

## 2. Audit of Existing Auth Test Suites (`services/api/tests/`)

| Test File | Existing Tests | Key Invariants Covered | Identified Gaps Prior to PH03 A07 |
|---|---|---|---|
| `test_auth_and_rbac.py` | 4 tests | Researcher role inference; search access for normal user & doctor; invalid bearer token rejected. | Did not test expired access tokens vs expired refresh tokens; did not test cookie auth isolation when invalid bearer header is present. |
| `test_auth_security_hardening.py` | 6 tests | Single-use refresh token; login rate limiter (3 attempts, 120s lockout); role override blocked in production; legal terms required in prod; distributed Redis lockout. | Focused on brute-force lockout and production role protection; lacked tests for secret key rotation grace periods and claim tampering. |
| `test_auth_extended_flow.py` | 3 tests | User registration and email verification; forgot/reset password flow; refresh token rotation and blocked reuse after logout. | Did not test silent refresh lifecycle where expired access token triggers automatic refresh and replay. |
| `test_auth_me_and_mobile_summary.py` | 13 tests | Medical disclaimer consent flow; `/auth/me` cookie vs bearer; cookie preference over stale body token; mobile summary feature flags by role. | Did not test token claim corruption (typ/iss tampering) or expired cookie handling on `/auth/me`. |
| `test_auth_email_delivery.py` | 6 tests | Email verification required; SMTP token redaction in logs; email dispatch on registration. | Dedicated to outbound email sanitization; no session UX coverage. |
| `hardening/test_authz_under_privileged.py` | 6 tests | Negative authorization testing; under-privileged role denial (403); missing credential denial (401). | Tests route authorization gates rather than token lifecycle and expiration mechanisms. |

---

## 3. Implemented Deliverables

### 3.1 Backend Session UX & Token Lifecycle Suite (`services/api/tests/test_auth_session_ux_states.py`)

A new, focused pytest module containing **14 automated tests**:

1. `TestTokenExpirationAndRejection`:
   - `test_expired_access_token_rejected_on_protected_endpoints`: Verified 401 with `"Token không hợp lệ hoặc đã hết hạn"` on `/auth/me` via both Bearer header and `clara_access_token` cookie.
   - `test_expired_refresh_token_rejected_on_refresh`: Verified 401 on `/auth/refresh` when presenting expired refresh token.
   - `test_decode_access_token_raises_http_401_on_expired`: Unit verification of `decode_access_token`.
   - `test_decode_refresh_token_raises_http_401_on_expired`: Unit verification of `decode_refresh_token`.
2. `TestSilentRefreshLifecycle`:
   - `test_silent_refresh_flow_recovers_expired_access_session`: Simulates full cycle of expired access token -> call `/auth/refresh` -> receive rotated tokens -> replay request with fresh access token -> 200 OK.
   - `test_both_tokens_expired_fails_closed`: Verifies that when both tokens are expired, refresh fails closed with 401.
3. `TestTokenClaimsAndIntegrity`:
   - `test_refresh_token_rejected_when_presented_as_access_token`: Type confusion prevention (`typ: refresh` rejected on `/auth/me`).
   - `test_access_token_rejected_when_presented_to_refresh_endpoint`: Type confusion prevention (`typ: access` rejected on `/auth/refresh`).
   - `test_wrong_issuer_token_is_rejected`: Issuer validation guard (`iss` mismatch rejected).
   - `test_tampered_signature_is_rejected`: Key tampering fails closed.
4. `TestSecretKeyRotationGracePeriod`:
   - `test_previous_key_token_accepted_during_rotation_window`: Validates that `JWT_SECRET_KEY_PREVIOUS` allows valid tokens to authenticate without mass session revocation during rotation. Once retired, old tokens fail closed.
5. `TestCookieBearerIsolation`:
   - `test_invalid_bearer_fails_without_falling_back_to_valid_cookie`: Crucial security invariant: a request with an invalid Authorization header never falls back to an ambient cookie.
   - `test_cookie_only_request_succeeds_when_header_absent`: Pure cookie-based session operates smoothly.
6. `TestCsrfSilentRefreshInteraction`:
   - `test_refresh_rotates_csrf_token`: Validates CSRF double-submit cookie rotation upon token refresh.

### 3.2 Web E2E Session Handling Suite (`apps/web/e2e/session-ux.spec.ts`)

A new Playwright E2E specification covering browser session UX states:
1. **Silent Refresh Recovery**: Intercepts 401 on initial `/auth/me`, executes single-flight `POST /auth/refresh`, and transparently recovers the session on `/today` without bouncing the user.
2. **Expired Session Redirection**: Intercepts failed refresh (401), validates redirect to `/login` preserving destination in `?next=%2Ftoday%3Ftab%3Dschedule`.
3. **Public Route Immunity**: Asserts that public surfaces (`/huong-dan`, `/legal/privacy`, `/legal/terms`) are completely immune to background 401 auth failures and never kick the visitor.
4. **Clean Logout**: Dispatches `beginLogout()`, ensures `POST /auth/logout` sets cookie expiry (`Max-Age=0`), purges tokens, and redirects cleanly.

---

## 4. Test Execution & Evidence

### 4.1 Pytest Execution: New Session UX Tests
- **Command:** `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test_auth.db" python3 -m pytest -v tests/test_auth_session_ux_states.py`
- **Working Directory:** `/dev/shm/clara_worktrees/PH03_A07/services/api`
- **Exit Code:** `0`
- **Results:**
  ```text
  tests/test_auth_session_ux_states.py::TestTokenExpirationAndRejection::test_expired_access_token_rejected_on_protected_endpoints PASSED [  7%]
  tests/test_auth_session_ux_states.py::TestTokenExpirationAndRejection::test_expired_refresh_token_rejected_on_refresh PASSED [ 14%]
  tests/test_auth_session_ux_states.py::TestTokenExpirationAndRejection::test_decode_access_token_raises_http_401_on_expired PASSED [ 21%]
  tests/test_auth_session_ux_states.py::TestTokenExpirationAndRejection::test_decode_refresh_token_raises_http_401_on_expired PASSED [ 28%]
  tests/test_auth_session_ux_states.py::TestSilentRefreshLifecycle::test_silent_refresh_flow_recovers_expired_access_session PASSED [ 35%]
  tests/test_auth_session_ux_states.py::TestSilentRefreshLifecycle::test_both_tokens_expired_fails_closed PASSED [ 42%]
  tests/test_auth_session_ux_states.py::TestTokenClaimsAndIntegrity::test_refresh_token_rejected_when_presented_as_access_token PASSED [ 50%]
  tests/test_auth_session_ux_states.py::TestTokenClaimsAndIntegrity::test_access_token_rejected_when_presented_to_refresh_endpoint PASSED [ 57%]
  tests/test_auth_session_ux_states.py::TestTokenClaimsAndIntegrity::test_wrong_issuer_token_is_rejected PASSED [ 64%]
  tests/test_auth_session_ux_states.py::TestTokenClaimsAndIntegrity::test_tampered_signature_is_rejected PASSED [ 71%]
  tests/test_auth_session_ux_states.py::TestSecretKeyRotationGracePeriod::test_previous_key_token_accepted_during_rotation_window PASSED [ 78%]
  tests/test_auth_session_ux_states.py::TestCookieBearerIsolation::test_invalid_bearer_fails_without_falling_back_to_valid_cookie PASSED [ 85%]
  tests/test_auth_session_ux_states.py::TestCookieBearerIsolation::test_cookie_only_request_succeeds_when_header_absent PASSED [ 92%]
  tests/test_auth_session_ux_states.py::TestCsrfSilentRefreshInteraction::test_refresh_rotates_csrf_token PASSED [100%]
  ======================== 14 passed, 1 warning in 11.36s ========================
  ```

### 4.2 Pytest Execution: Full Combined Auth Test Suite
- **Command:** `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test_auth.db" python3 -m pytest -q tests/test_auth_and_rbac.py tests/test_auth_security_hardening.py tests/test_auth_extended_flow.py tests/test_auth_me_and_mobile_summary.py tests/test_auth_email_delivery.py tests/hardening/test_authz_under_privileged.py tests/test_auth_session_ux_states.py`
- **Working Directory:** `/dev/shm/clara_worktrees/PH03_A07/services/api`
- **Exit Code:** `0`
- **Results:**
  ```text
  ......................................................                   [100%]
  54 passed, 1 warning in 48.82s
  ```

### 4.3 Ruff Linter Execution
- **Command:** `ruff check tests/test_auth_session_ux_states.py`
- **Exit Code:** `0`
- **Result:** `All checks passed!`

---

## 5. Summary & Verification Verdict

All 54 backend authentication, authorization, session UX, and token lifecycle tests pass cleanly with zero failures. Both backend API session contracts and frontend browser E2E session specifications are in place, tested, and conformant with CLARA's regression-locked safety invariants.
