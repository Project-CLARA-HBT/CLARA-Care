# PH03 / A07 — Risk Register: Web Session UX & Auth Test Audit

**Phase:** PH03 (Hardening auth và identity)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Overview

This risk register documents operational, security, and user experience risks surrounding web session states, silent refresh loops, token invalidation, and automated verification suites in PH03.

---

## 2. Risk Matrix & Mitigations

### RISK-AUTH-01: Silent Refresh Infinite Loop on Persistent Auth Failure
- **Category:** User Experience / Denial of Service
- **Severity:** HIGH (P1)
- **Description:**
  If the HTTP client automatically retries failed 401 requests via silent refresh, and the refresh endpoint itself returns 401 or network errors, a poorly-guarded interceptor could loop indefinitely, spamming the server and freezing the browser UI.
- **Compensating Controls:**
  1. `apps/web/lib/http-client.ts` tags requests with `_retry: boolean`. Only one retry is permitted per request.
  2. `ensureSingleFlightRefresh()` collapses concurrent 401 triggers into a single in-flight Promise.
  3. If refresh fails, `bestEffortServerLogout()` is called, tokens are purged from memory/storage, and the user is redirected via `redirectToLoginAfterAuthFailure()`.
  4. Verified in `apps/web/e2e/session-ux.spec.ts` ("expired refresh redirects to /login").

---

### RISK-AUTH-02: Public Route Bounce / Denial of Service on Background 401
- **Category:** User Experience / Usability
- **Severity:** MEDIUM (P2)
- **Description:**
  Unauthenticated visitors browsing public routes (e.g. `/`, `/huong-dan`, `/legal/privacy`, `/legal/terms`) could trigger background polling or optional profile checks. If a background 401 causes an unconditioned redirect to `/login`, the visitor is abruptly kicked from public documentation.
- **Compensating Controls:**
  1. `AUTH_FAILURE_REDIRECT_SKIP_PREFIXES` in `apps/web/lib/http-client.ts` explicitly protects public routes and prefixes.
  2. `SessionBoundary` checks `isPublicRoute(pathname)` and avoids login redirects on public pages.
  3. Verified in `apps/web/e2e/session-ux.spec.ts` ("public routes never bounce to /login even if a background call receives 401").

---

### RISK-AUTH-03: Confused Deputy Fallback between Bearer and Cookie Auth
- **Category:** Security / Session Fixation & CSRF
- **Severity:** CRITICAL (P0)
- **Description:**
  If a client presents a malformed or expired Bearer token in the `Authorization` header, the server must NOT fall back to an ambient cookie session to fulfill the request. Doing so violates credential isolation and weakens CSRF protections.
- **Compensating Controls:**
  1. `clara_api.core.security` and authentication dependencies enforce strict fail-closed evaluation: when `Authorization` is provided, it is evaluated strictly. Any invalid Bearer token immediately raises HTTP 401 without falling back to cookies.
  2. Verified in `services/api/tests/test_auth_session_ux_states.py` (`TestCookieBearerIsolation.test_invalid_bearer_fails_without_falling_back_to_valid_cookie`).

---

### RISK-AUTH-04: Mass Session Revocation during Key Rotation
- **Category:** Operational Availability
- **Severity:** MEDIUM (P2)
- **Description:**
  When rotating `JWT_SECRET_KEY`, abruptly changing the key immediately invalidates all active access and refresh tokens, terminating all active user sessions simultaneously.
- **Compensating Controls:**
  1. `clara_api.core.security` implements dual-key verification via `_signing_keys()` using `JWT_SECRET_KEY` (signing and verification) and `JWT_SECRET_KEY_PREVIOUS` (verification only).
  2. Tokens minted under the previous key remain valid until natural expiration during the transition window.
  3. Verified in `services/api/tests/test_auth_session_ux_states.py` (`TestSecretKeyRotationGracePeriod.test_previous_key_token_accepted_during_rotation_window`).

---

### RISK-AUTH-05: Local Database Concurrency Lockout during CI Test Execution
- **Category:** Tooling / CI Flakiness
- **Severity:** LOW (P3)
- **Description:**
  Concurrent execution of pytest against shared `/tmp/clara_api_ci.db` on low-resource or slow disk environments can cause SQLite table lock timeouts.
- **Compensating Controls:**
  1. Pytest configuration supports overriding `CLARA_TEST_DATABASE_URL` with dedicated in-memory or tmpfs paths (e.g. `/dev/shm/clara_test_auth.db`).
  2. Fixtures in `conftest.py` ensure clean row deletion and table isolation per test session.
