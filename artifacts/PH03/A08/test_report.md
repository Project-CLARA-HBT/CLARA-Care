# Test Report: Mobile Refresh & Session Persistence Security Audit

**Phase:** PH03
**Subagent:** A08
**Role:** Security + privacy
**Base SHA / HEAD SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
**Execution Timestamp:** 2026-10-21T21:40:00Z

---

## 1. Test Summary Overview

| Test Suite / Command | Scope / Purpose | Exit Code | Status | Duration |
|---|---|---|---|---|
| `python3 -m evaluation.commitloop.secret_scan --repo-root .` | Fail-closed repository-wide secret scanning | `0` | PASS | 0.8s |
| `python3 scripts/security/redteam_manifest_checker.py artifacts/PH00 artifacts/PH01 artifacts/PH02` | Deterministic red-team deliverable verification across 30 historical subagents | `0` | PASS | 0.2s |
| `python3 scripts/ops/audit_mobile_auth_session_security.py` | Automated security inspection of mobile refresh, storage, and logging | `0` | PASS | 0.3s |
| `pytest -v scripts/ops/test_audit_mobile_auth_session_security.py` | Unit tests for mobile auth auditor (clean fixture, flawed fixture, repo scan) | `0` | PASS | 0.4s |
| `python3 -m py_compile scripts/ops/audit_mobile_auth_session_security.py scripts/ops/test_audit_mobile_auth_session_security.py` | Python AST compilation verification | `0` | PASS | 0.1s |
| `python3 scripts/security/check_ci_artifact_policy.py` | CI artifact and credential policy enforcement | `0` | PASS | 0.1s |
| `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions` | Alembic migration downgrade safety verification | `0` | PASS | 0.2s |

---

## 2. Command Process Outputs

### 2.1 Secret Scan
```text
$ python3 -m evaluation.commitloop.secret_scan --repo-root .
secret_scan_passed
```

### 2.2 Red-Team Manifest Checker
```text
$ python3 scripts/security/redteam_manifest_checker.py artifacts/PH00 artifacts/PH01 artifacts/PH02
================================================================================
DETERMINISTIC RED-TEAM MANIFEST CHECKER
Manifests Audited: 30
Overall Status:    PASSED
Findings Summary:  CRITICAL=0, HIGH=0, MEDIUM=0, LOW=0
================================================================================
[PASSED] Phase: PH00   Agent: A01    -> artifacts/PH00/A01/change_manifest.json
...
[PASSED] Phase: PH02   Agent: A10    -> artifacts/PH02/A10/change_manifest.json
================================================================================
```

### 2.3 Mobile Auth Security Auditor
```text
$ python3 scripts/ops/audit_mobile_auth_session_security.py
================================================================================
CLARA MOBILE AUTH, REFRESH ROTATION & SESSION PERSISTENCE SECURITY AUDIT
================================================================================
Repository Root: /dev/shm/clara_worktrees/PH03_A08
Total Findings Detected: 6 (Filtered by >=LOW: 6)
================================================================================
[1] MOB-AUTH-02: Session Wiped on Transient Network Failure During Refresh (MEDIUM)
    Category:     REFRESH_ROTATION
    Location:     apps/mobile/lib/core/api_client.dart:2749
    Code Anchor:  _doRefresh() catch block
    Description:  Transient socket timeout or offline disconnect during refresh immediately clears user credentials.
    Impact:       Poor user resilience: user forced to re-login on flaky network connections.
    Remediation:  Distinguish network/transport exceptions from 401/403 responses. Only clear session on terminal auth rejections.
--------------------------------------------------------------------------------
[2] MOB-AUTH-03: Premature Session Eviction on Launch Without Refresh Attempt (HIGH)
    Category:     REFRESH_ROTATION
    Location:     apps/mobile/lib/core/session_store.dart:112
    Code Anchor:  hydrate() -> if (isExpired) await clear();
    Description:  On cold start, if the access token has expired, hydrate() clears all stored credentials, discarding the valid refresh token without attempting an exchange.
    Impact:       User session does not survive beyond access token lifetime (15-30m) across app restarts, undermining mobile session persistence.
    Remediation:  Preserve valid refresh tokens during hydrate, or trigger background refresh before evicting the session.
--------------------------------------------------------------------------------
[3] MOB-STORAGE-01: Android Auto-Backup Exposure for Sensitive App Data (HIGH)
    Category:     SECURE_STORAGE
    Location:     apps/mobile/android/app/src/main/AndroidManifest.xml:3
    Code Anchor:  <application ...>
    Description:  AndroidManifest.xml omits android:allowBackup="false", defaulting to true. This permits extraction of app data via adb backup and Google Cloud Backup.
    Impact:       Potential extraction of cached medical information and shared preferences on unencrypted backups.
    Remediation:  Explicitly set android:allowBackup="false" in AndroidManifest.xml and configure dataExtractionRules.
--------------------------------------------------------------------------------
[4] MOB-STORAGE-02: FlutterSecureStorage Omits Hardened Android/iOS Options (MEDIUM)
    Category:     SECURE_STORAGE
    Location:     apps/mobile/lib/core/session_store.dart:19
    Code Anchor:  FlutterSecureSessionStorage constructor
    Description:  FlutterSecureStorage is instantiated with default options, lacking AndroidOptions(encryptedSharedPreferences: true, resetOnError: true) and iOS KeychainAccessibility controls.
    Impact:       Risk of unhandled KeyStore corruption crashes on Android OEM updates, and suboptimal keychain accessibility boundaries on iOS.
    Remediation:  Configure AndroidOptions(encryptedSharedPreferences: true, resetOnError: true) and IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device).
--------------------------------------------------------------------------------
[5] MOB-LOG-01: Analytics PII Denylist Missing Bearer Token Key Filters (HIGH)
    Category:     LOGGING_LEAK
    Location:     apps/mobile/lib/core/analytics.dart:286
    Code Anchor:  _deniedExactKeys / _deniedSubstrings
    Description:  Analytics property sanitization lacks token-specific redaction keywords: authorization.
    Impact:       Accidental inclusion of token attributes in custom event payloads would be transmitted to external analytics providers.
    Remediation:  Add 'token', 'accesstoken', 'refreshtoken', 'bearer', 'secret', and 'auth' to _deniedSubstrings and _deniedExactKeys.
--------------------------------------------------------------------------------
[6] SRV-AUTH-02: Incomplete Token Family Revocation on Replay Detection (MEDIUM)
    Category:     SERVER_CONTRACT
    Location:     services/api/src/clara_api/core/session_security.py:161
    Code Anchor:  record_reuse()
    Description:  When a replayed refresh token is detected, the server rejects the request and increments a counter, but does not invalidate the legitimate descendant token issued during the initial rotation.
    Impact:       Breach of RFC 6749 §10.4 token family revocation recommendation: compromised session remains active for the holder of the rotated token.
    Remediation:  Implement family-wide token revocation tying rotated descendants to parent lineage marker.
--------------------------------------------------------------------------------
```

### 2.4 Auditor Unit Tests
```text
$ pytest -v scripts/ops/test_audit_mobile_auth_session_security.py
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /dev/shm/clara_worktrees/PH03_A08
plugins: anyio-4.14.2, asyncio-1.4.0, hypothesis-6.167.1
asyncio: mode=Mode.STRICT, debug=False
collected 3 items

scripts/ops/test_audit_mobile_auth_session_security.py::test_auditor_runs_against_repo PASSED [ 33%]
scripts/ops/test_audit_mobile_auth_session_security.py::test_auditor_detects_clean_fixture PASSED [ 66%]
scripts/ops/test_audit_mobile_auth_session_security.py::test_auditor_detects_flawed_fixture PASSED [100%]

============================== 3 passed in 0.35s ===============================
```

---

## 3. Verification Conclusion

All security scans, manifest validations, and auditor tests completed cleanly with exit code 0.
The security audit documentation, operational audit tool, and test cases have been authored and verified within the designated path lanes.
