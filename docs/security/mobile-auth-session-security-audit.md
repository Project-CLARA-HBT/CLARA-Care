# Mobile Refresh Token, Session Persistence & Key Storage Security Audit

**Audit Phase:** PH03
**Auditor / Agent:** A08 (Security + Privacy)
**Date:** 2026-10-21
**Target Scope:** `apps/mobile/lib/core/`, `apps/mobile/android/`, `services/api/src/clara_api/api/v1/endpoints/auth.py`, `services/api/src/clara_api/core/session_security.py`
**Standards:** RFC 6749 §10.4 (OAuth 2.0 Token Revocation/Rotation), OWASP MASVS (v2.0: MASVS-AUTH, MASVS-STORAGE, MASVS-CODE), NIST SP 800-63B

---

## 1. Executive Summary

This security audit inspects mobile session persistence, refresh token rotation semantics, secure key storage mechanisms, and token leakage vectors in logs/telemetry across CLARA Mobile and its backend API contract.

### Key Audit Findings Matrix

| Finding ID | Title | Severity | Category | Status | Primary Location |
|---|---|---|---|---|---|
| **MOB-AUTH-01** | Refresh Request Coalescing (Single In-Flight) | INFO (Compliant) | REFRESH_ROTATION | Pass | `apps/mobile/lib/core/api_client.dart:2736-2747` |
| **MOB-AUTH-02** | Session Wiped on Transient Network Failure During Refresh | MEDIUM | REFRESH_ROTATION | Tracked Remediation | `apps/mobile/lib/core/api_client.dart:2771-2775` |
| **MOB-AUTH-03** | Premature Session Eviction on Launch Without Refresh Attempt | HIGH | REFRESH_ROTATION | Tracked Remediation | `apps/mobile/lib/core/session_store.dart:129-135` |
| **MOB-AUTH-04** | Offline Cache Evicted on In-Session Token Refresh | MEDIUM | REFRESH_ROTATION | Tracked Remediation | `apps/mobile/lib/core/session_store.dart:146-149` |
| **MOB-STORAGE-01** | Android Auto-Backup Exposure for App Data | HIGH | SECURE_STORAGE | Tracked Remediation | `apps/mobile/android/app/src/main/AndroidManifest.xml:3` |
| **MOB-STORAGE-02** | Default Hardware Key Options in FlutterSecureStorage | MEDIUM | SECURE_STORAGE | Tracked Remediation | `apps/mobile/lib/core/session_store.dart:19-24` |
| **MOB-LOG-01** | Analytics Property Denylist Missing Explicit Token Filters | HIGH | LOGGING_LEAK | Tracked Remediation | `apps/mobile/lib/core/analytics.dart:286-364` |
| **MOB-LOG-02** | Production Logging Hygiene (Print Statements) | INFO (Compliant) | LOGGING_LEAK | Pass | `apps/mobile/lib/` (0 raw prints) |
| **MOB-LOG-03** | Public Share Link In-Memory Bounding | INFO (Compliant) | LOGGING_LEAK | Pass | `apps/mobile/lib/core/public_share_link.dart:27-50` |
| **SRV-AUTH-01** | Server Refresh Rotation and Replay Detection Integration | INFO (Compliant) | SERVER_CONTRACT | Pass | `services/api/src/clara_api/api/v1/endpoints/auth.py:757-824` |
| **SRV-AUTH-02** | Token Family Invalidation on Replay Detection | MEDIUM | SERVER_CONTRACT | Tracked Remediation | `services/api/src/clara_api/core/session_security.py:161-179` |

---

## 2. In-Depth Technical Analysis

### 2.1 Refresh Token Rotation & Race Prevention (RFC 6749 §10.4)

#### A. Coalescing Parallel Refreshes (`MOB-AUTH-01`)
- **Analysis:** In `apps/mobile/lib/core/api_client.dart:2736-2747`, `_attemptRefresh()` correctly checks `_refreshInFlight`. If an existing Future is active, subsequent calls await the identical Future.
- **Verification:** Unit tests in `apps/mobile/test/api_client_token_refresh_test.dart:301-330` confirm that concurrent expired requests trigger exactly 1 network call to `/api/v1/auth/refresh`.
- **Finding:** Verified secure and compliant. Prevents stampedes and accidental reuse detection triggers.

#### B. Transient Error Handling During Refresh (`MOB-AUTH-02`)
- **Vulnerability:** In `apps/mobile/lib/core/api_client.dart:2771-2775`:
  ```dart
  try {
    response = await _withTimeout(_httpClient.post(...));
  } catch (_) {
    // Timeout / transport error during refresh -> clear (Req 6.3).
    await hooks.onSessionCleared();
    return null;
  }
  ```
- **Risk:** If a device briefly enters an elevator, tunnel, or cell-tower handoff while executing a background refresh, a network timeout immediately invokes `onSessionCleared()`, logging the user out.
- **Remediation Plan:** Differentiate between network transport errors (`SocketException`, `TimeoutException`) and terminal HTTP 401/403 responses. Only purge session state on definitive server authorization rejections.

#### C. Cold Start Session Hydration (`MOB-AUTH-03`)
- **Vulnerability:** In `apps/mobile/lib/core/session_store.dart:129-135`:
  ```dart
  if (isExpired) {
    await clear();
    return;
  }
  ```
  `isExpired` inspects only `accessToken`. In production, access tokens typically have a short TTL (e.g. 15-30 minutes), whereas refresh tokens have a long TTL (e.g. 30 days). When a user relaunches the app after 30 minutes, `isExpired` evaluates to `true` and clears the valid `refreshToken` before the app even attempts a refresh.
- **Remediation Plan:** During `hydrate()`, if the access token is expired but a valid refresh token exists, retain credentials in memory and trigger an automatic background refresh rather than evicting the session.

#### D. Unintended Offline Cache Purging (`MOB-AUTH-04`)
- **Vulnerability:** In `apps/mobile/lib/core/session_store.dart:146-149`:
  ```dart
  if (_email != null || _accessToken != null) {
    await _purgeOfflineCaches(email: _email, token: _accessToken);
  }
  ```
  When `setSession` is called during a routine in-session token refresh (`onSessionRefreshed`), `_email` is already populated. Calling `_purgeOfflineCaches()` wipes the user's CareGuard and LifeMap offline caches even though the user identity did not change.
- **Remediation Plan:** Condition `_purgeOfflineCaches()` on user identity change: `if (_email != null && _email != newEmail)`.

---

### 2.2 Secure Storage Architecture (OWASP MASVS-STORAGE)

#### A. Android Auto-Backup Exposure (`MOB-STORAGE-01`)
- **Vulnerability:** `apps/mobile/android/app/src/main/AndroidManifest.xml` does not set `android:allowBackup="false"`. On Android devices, ADB backups or Google Cloud Auto-Backup can back up application sandbox data.
- **Remediation Plan:** Set `android:allowBackup="false"` or configure `android:dataExtractionRules` to exclude all shared preferences, secure storage databases, and cache directories from cloud and device-to-device migration.

#### B. FlutterSecureStorage Configuration (`MOB-STORAGE-02`)
- **Vulnerability:** `FlutterSecureSessionStorage` initializes `const FlutterSecureStorage()` without platform-specific hardening parameters:
  - Missing Android options: `AndroidOptions(encryptedSharedPreferences: true, resetOnError: true)`.
  - Missing iOS options: `IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device)`.
- **Remediation Plan:** Update `FlutterSecureSessionStorage` constructor to specify hardened options, preventing KeyStore decryption exceptions upon Android OS upgrades and securing Keychain item accessibility.

---

### 2.3 Token Leakage in Logging & Analytics (OWASP MASVS-CODE)

#### A. Analytics Property Redaction (`MOB-LOG-01`)
- **Vulnerability:** `apps/mobile/lib/core/analytics.dart` filters PII via `_deniedExactKeys` and `_deniedSubstrings`. While comprehensive for patient/clinical data (`email`, `phone`, `drug`, `symptom`, `query`), it omits explicit token keywords such as `token`, `bearer`, `refreshtoken`, `accesstoken`, `auth`, `authorization`, `secret`.
- **Remediation Plan:** Extend `_deniedExactKeys` and `_deniedSubstrings` in `analytics.dart` to include all authorization and bearer capability tokens.

#### B. Console Logging Hygiene (`MOB-LOG-02`)
- **Analysis:** Scanned all `.dart` files under `apps/mobile/lib/`. Zero raw `print(...)` statements exist in production code. All error handling uses typed exceptions or structured callbacks.
- **Finding:** Clean.

#### C. Public Share Link Capability Protection (`MOB-LOG-03`)
- **Analysis:** `apps/mobile/lib/core/public_share_link.dart` implements strict defensive bounds:
  - Canonical domain validation: whitelist restricted to `theclaracare.com` and `www.theclaracare.com`.
  - HTTPS enforcement: non-HTTPS links are rejected.
  - Length bound: token length capped at 512 characters.
  - Memory-only capability: never written to storage, flushed immediately upon view close.
- **Finding:** Clean and well-engineered.

---

### 2.4 Server-Side Verification Contract

#### A. Replay Detection & Rotation Execution (`SRV-AUTH-01`)
- **Analysis:** `services/api/src/clara_api/api/v1/endpoints/auth.py:757-824` implements robust refresh-token rotation when `hardening_refresh_rotation_enabled` is active:
  - Scans candidate tokens and extracts `jti`.
  - Consults `session_security.is_refresh_reused(candidate_jti)`.
  - On reuse detection, logs no-PII warning, increments counter, clears auth cookies, and raises HTTP 401.
  - Rotates refresh token via `session_security.rotate_refresh(...)`, recording SHA-256 digests in Redis with TTL.
- **Finding:** Verified secure.

#### B. Token Family Invalidation (`SRV-AUTH-02`)
- **Vulnerability:** RFC 6749 §10.4 recommends that upon detecting refresh token replay, the authorization server should invalidate the entire token family (all refresh tokens issued within that lineage). Currently, `record_reuse()` logs the event and rejects the replay, but does not invalidate the newest descendant refresh token already held by the legitimate client or attacker.
- **Remediation Plan:** Implement token family lineage tracking in Redis to invalidate all descendants upon replay detection.

---

## 3. Operational Checklists & Artifacts

1. Automated audit script created: `scripts/ops/audit_mobile_auth_session_security.py` (executable, test-backed).
2. Automated test suite created: `scripts/ops/test_audit_mobile_auth_session_security.py` (3/3 unit tests passing).
3. Privacy checklist updated: `docs/security/privacy-checklist.md` with explicit mobile session, storage, and token redaction invariants.
