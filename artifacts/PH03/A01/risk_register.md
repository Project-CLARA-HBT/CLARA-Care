# PH03-A01 Risk Register & Threat Inventory Log

- **Phase:** PH03 (Hardening Auth và Identity)
- **Agent:** A01 (API + contract)
- **Worktree:** `/dev/shm/clara_worktrees/PH03_A01`
- **Branch:** `phase/ph03-a01`
- **Base Commit SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
- **Frozen HEAD SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
- **Status:** **PASSED**
- **Date:** 2026-10-21

---

## 1. Executive Summary & Threat Profile

Subagent **A01** executed the comprehensive **Authentication Threat Inventory** task for CLARA Care across:
1. `services/api/src/clara_api/api/v1/endpoints/auth.py` (FastAPI authentication & authorization endpoints)
2. `services/api/src/clara_api/schemas.py` (Pydantic request/response schemas)
3. `services/api/src/clara_api/core/security.py`, `rbac.py`, `login_guard.py`, `session_security.py`
4. Token contracts and cryptographic boundaries (`contracts/auth/token-contract.schema.json`)

The inventory rigorously examines the 4 mandated core threat vectors:
- **Credential Stuffing & Brute Force**
- **Token Replay & State De-synchronization**
- **JWT Forgery & Algorithm Confusion**
- **Timing Attacks & Side-Channel Information Leakage**

---

## 2. Comprehensive Threat Inventory Matrix

| Threat Vector ID | Threat Name | STRIDE Category | Severity | Likelihood | Impact | Current Controls & Defenses | Residual Gaps / Hardening Recommendations |
|---|---|---|---|---|---|---|---|
| **TV-AUTH-01** | **Credential Stuffing & Dictionary Attacks** | Spoofing / Denial of Service | **HIGH** | High | High | • `LoginGuard` in-memory / distributed Redis bucket per `email \| client_ip`<br>• Linear block window (15m window, 5 attempts -> 900s block)<br>• Action rate-limiting on sensitive pre-auth operations (`_ensure_action_rate_limit`) | • IP spoofing possible if reverse proxy headers (`X-Forwarded-For`) are trusted without CIDR validation<br>• Account enumeration possible via response timing differences on non-existent vs bad password users |
| **TV-AUTH-02** | **Session Replay & Refresh Reuse** | Spoofing / Elevation of Privilege | **HIGH** | Medium | Critical | • Single-use refresh token consumption in DB (`AuthToken.used_at` flag)<br>• JTI generation via `secrets.token_urlsafe(12)`<br>• Hardening refresh rotation flag (`hardening_refresh_rotation_enabled`) with Redis reuse detection markers | • If `hardening_refresh_rotation_enabled` is false, refresh token can be replayed until consumed or expired<br>• Stateless access token (15m) cannot be immediately invalidated unless denylist flag (`hardening_token_denylist_enabled`) is turned on |
| **TV-AUTH-03** | **JWT Forgery & Key/Algorithm Confusion** | Spoofing / Tampering | **CRITICAL** | Low | Critical | • Explicit `algorithms=[settings.jwt_algorithm]` in `jwt.decode` prevents `none` algorithm exploit<br>• `_signing_keys` dual-key verification during rotation (`jwt_secret_key_previous`)<br>• Strict claim validation: `iss`, `typ`, `sub`, `role`, `exp` enforced in `decode_access_token` and `decode_refresh_token` | • Secret key rotation relies on manual environment configuration without automated JWKS federation<br>• Symmetric HS256 requires sharing secret between microservices if ML/OCR verify tokens independently (API central gateway currently mitigates this) |
| **TV-AUTH-04** | **Timing Attacks & Side-Channel Leakage** | Information Disclosure | **MEDIUM** | Medium | Low | • Constant-time comparison for password verification via `hmac.compare_digest` in `clara_api/core/passwords.py`<br>• Constant-time comparison for cookie/payload refresh token conflict via `secrets.compare_digest`<br>• Token hashes use SHA-256 digests (`_hash_action_token`) | • Password hashing PBKDF2 (390,000 iterations) takes ~25-40ms. If user does not exist, `login()` returns immediately without hashing, leaking whether the email is registered via response latency |
| **TV-AUTH-05** | **CSRF via Cookie-Authenticated Sessions** | Spoofing / Tampering | **HIGH** | Low | High | • Double-submit CSRF cookie pattern (`auth_csrf_enabled`)<br>• SameSite cookie attributes (`Lax`/`Strict`) and `HttpOnly` flags<br>• Strict exemption parsing: malformed/expired bearer tokens never downgrade to cookie auth | • Subdomains can overwrite non-host-prefixed cookies if cookie domain is broad |
| **TV-AUTH-06** | **Action Token Tampering (Email/OTP/Reset)** | Spoofing / Elevation of Privilege | **HIGH** | Low | High | • Stored as SHA-256 digests in `AuthToken`<br>• Single-use consumption via `used_at = now`<br>• Explicit TTL (default 15 minutes) and scheduled cleanup | • 6-digit numeric OTP for doctors/admins (`1_000_000` space) requires strict rate limiting per email+IP to prevent online brute force |

---

## 3. Deep-Dive Threat Analysis

### 3.1 Credential Stuffing & Brute Force Analysis
- **Code Anchor:** `services/api/src/clara_api/api/v1/endpoints/auth.py:536-628` (`login`), `services/api/src/clara_api/core/login_guard.py:20-115` (`LoginGuard`).
- **Mechanisms:**
  - `login_guard.is_blocked(login_key)` checks whether an IP/email pair has exceeded `auth_login_attempt_limit` (default 5 attempts in 15 minutes).
  - When locked, returns `HTTP 429 Too Many Requests` with retry cooldown.
  - Fail-closed mode available via `hardening_login_fail_closed` to prevent fallback to allow-all when Redis is unreachable.
- **Vulnerabilities / Risks:**
  - Distributed credential stuffing across broad botnets (rotating IP per attempt) targets a single victim email with 1 attempt per IP. The composite key `normalized_email|ip` permits distributed brute force across multiple IPs.
  - **Remediation Recommendation:** Add secondary global account-level velocity limit (`email_fail_counter`) regardless of client IP.

### 3.2 Token Replay & State De-synchronization
- **Code Anchor:** `services/api/src/clara_api/api/v1/endpoints/auth.py:738-825` (`refresh_token`), `services/api/src/clara_api/core/session_security.py:41-182` (`SessionSecurity`).
- **Mechanisms:**
  - Refresh tokens are tracked in `auth_tokens` table with SHA-256 hashed values.
  - `_consume_refresh_session_token` sets `used_at = now`, preventing database replay.
  - Hardening flag `hardening_refresh_rotation_enabled`: when active, records old JTI in Redis (`refresh:rot:<hash>`). If presented again, triggers `session_security.record_reuse()`, revokes session cookies, and fails closed with 401.
- **Vulnerabilities / Risks:**
  - In a clustered multi-datacenter deployment without shared Redis, concurrent refresh calls could race before database commit.
  - **Remediation Recommendation:** Ensure database transaction isolation or row locking (`with_for_update`) on `AuthToken` during refresh consumption.

### 3.3 JWT Forgery & Key Compromise
- **Code Anchor:** `services/api/src/clara_api/core/security.py:21-118`.
- **Mechanisms:**
  - `jwt.decode` enforces `algorithms=[settings.jwt_algorithm]` (HS256 by default), entirely preventing algorithm confusion (e.g. `none` or RSA->HMAC public key confusion).
  - Type discriminator `typ: "access"` vs `typ: "refresh"` prevents an access token from being supplied to the refresh endpoint or vice versa.
  - Dual-key fallback allows seamless zero-downtime key rotation via `jwt_secret_key_previous`.
- **Vulnerabilities / Risks:**
  - In non-production environments, default fallback keys like `"dev-secret-key-clara-2026-development-only"` may be insecure if accidentally exposed in staging configs.
  - **Remediation Recommendation:** Enforce minimum entropy checks for `JWT_SECRET_KEY` during application startup in production mode.

### 3.4 Timing Attacks & Side-Channel Profiling
- **Code Anchor:** `services/api/src/clara_api/core/passwords.py:15-27`, `services/api/src/clara_api/api/v1/endpoints/auth.py:556-581`.
- **Mechanisms:**
  - Password hash comparison uses `hmac.compare_digest(actual, expected)`, eliminating string byte comparison timing leaks.
  - Token lookup operates against SHA-256 pre-hashed records.
- **Vulnerabilities / Risks:**
  - In `login()`, user existence query executes first. If user is absent, endpoint immediately registers failure and returns 401 without running `verify_password()`.
  - Since `hash_password`/`verify_password` performs 390,000 PBKDF2 iterations (~30ms CPU time), an attacker can measure the 30ms latency delta to enumerate valid registered emails.
  - **Remediation Recommendation:** Execute a dummy PBKDF2 hash verification on a fixed constant salt when user lookup returns `None` to make user-exist vs user-absent response latency statistically indistinguishable.

---

## 4. Endpoints & Schemas Audited

1. `POST /api/v1/auth/register` (`RegisterRequest` -> `RegisterResponse`)
   - Mandatory email normalization, password complexity regex (digits + letters), rate limiting.
2. `POST /api/v1/auth/verify-email` (`VerifyEmailRequest` -> `dict`)
   - Consumes single-use SHA-256 hashed token with TTL.
3. `POST /api/v1/auth/login` (`LoginRequest` -> `LoginResponse`)
   - Guarded by `LoginGuard` brute force detector; optional OTP challenge for privileged roles (`doctor`, `admin`).
4. `POST /api/v1/auth/login-otp/verify` (`LoginOtpVerifyRequest` -> `LoginResponse`)
   - 6-digit OTP verification; rate limited per IP and email.
5. `POST /api/v1/auth/callback` (`AuthCallbackRequest` -> `LoginResponse`)
   - OAuth authorization code exchange; intentionally public.
6. `POST /api/v1/auth/refresh` (`RefreshTokenRequest` -> `LoginResponse`)
   - HttpOnly cookie preference, database token consumption, rotation and reuse detection.
7. `POST /api/v1/auth/forgot-password` (`ForgotPasswordRequest` -> `ForgotPasswordResponse`)
   - Blind acceptance pattern (`accepted=True`) prevents email enumeration.
8. `POST /api/v1/auth/resend-verification` (`ResendVerificationRequest` -> `ResendVerificationResponse`)
   - Blind acceptance pattern.
9. `POST /api/v1/auth/reset-password` (`ResetPasswordRequest` -> `dict`)
   - Single-use reset token consumption; enforces new password distinct from current; invalidates existing refresh sessions.
10. `POST /api/v1/auth/change-password` (`ChangePasswordRequest` -> `dict`)
    - Requires active session; validates current password; invalidates all refresh sessions.
11. `POST /api/v1/auth/logout` (None -> `dict`)
    - Clears cookies; revokes refresh tokens; denylists JTI when denylist enabled.
12. `GET /api/v1/auth/me` (None -> `dict`)
    - Role and identity projection; authenticated.
13. `GET /api/v1/auth/consent-status` & `POST /api/v1/auth/consent` (`ConsentAcceptRequest` -> `ConsentAcceptResponse`)
    - Versioned medical disclaimer gate with row-level mutex locking.

---

## 5. Residual Risk Summary

- **RR-PH03-A01-01 (Controlled):** Email enumeration via timing discrepancy during login. Mitigation planned for dummy-hash implementation in subsequent phase.
- **RR-PH03-A01-02 (Monitored):** 6-digit numeric OTP brute force space. Mitigated by `auth_action_rate_limit_attempts` (max 5 attempts).
- **RR-PH03-A01-03 (Controlled):** Token revocation requires Redis store; falls back to database token consumption when Redis is unavailable.
