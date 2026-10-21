# Risk Register: Mobile Refresh & Session Persistence Security

**Phase:** PH03
**Subagent:** A08
**Role:** Security + privacy
**Last Updated:** 2026-10-21

---

## Risk Matrix

| Risk ID | Vulnerability / Threat | Likelihood | Impact | Risk Level | Mitigation & Compensating Controls | Residual Risk | Owner |
|---|---|---|---|---|---|---|---|
| **RSK-MOB-01** | **Premature Session Clearing on Cold Start** (`MOB-AUTH-03`): `hydrate()` evicts valid refresh tokens when the access token expires prior to app relaunch. | HIGH | MEDIUM | **HIGH** | Refactor `hydrate()` to distinguish expired access tokens from expired refresh tokens; retain session in memory and trigger background refresh before evicting. | LOW | Mobile Core |
| **RSK-MOB-02** | **Android Sandbox Data Backup Leakage** (`MOB-STORAGE-01`): `AndroidManifest.xml` omits `android:allowBackup="false"`, allowing ADB and cloud backups of app storage. | MEDIUM | HIGH | **HIGH** | Set `android:allowBackup="false"` in `AndroidManifest.xml` and configure explicit XML data extraction exclusion rules. | LOW | Mobile Ops |
| **RSK-MOB-03** | **Analytics Token Leakage** (`MOB-LOG-01`): Custom analytics event payloads could transmit auth tokens if developer attaches credentials to event props. | LOW | HIGH | **MEDIUM** | Extend `_deniedExactKeys` and `_deniedSubstrings` in `apps/mobile/lib/core/analytics.dart` to filter `token`, `bearer`, `refreshtoken`, `accesstoken`, `auth`, `secret`. | NEGLIGIBLE | Analytics Eng |
| **RSK-MOB-04** | **Transient Network Disconnect Wiping Session** (`MOB-AUTH-02`): Network timeout during `POST /auth/refresh` immediately calls `onSessionCleared()`. | HIGH | LOW | **MEDIUM** | Catch transport/socket exceptions separately from 401/403 HTTP rejections; preserve session for offline retry. | LOW | Mobile Core |
| **RSK-MOB-05** | **Offline Cache Eviction on In-Session Refresh** (`MOB-AUTH-04`): `setSession()` clears offline CareGuard & LifeMap cache upon every refresh rotation. | HIGH | LOW | **MEDIUM** | Guard `_purgeOfflineCaches()` so it only fires if the user identity (`email` or `userId`) actually changed. | LOW | Mobile Core |
| **RSK-MOB-06** | **Incomplete Token Family Invalidation** (`SRV-AUTH-02`): Server detects refresh token replay but does not invalidate all descended tokens in the family. | LOW | HIGH | **MEDIUM** | Enhance Redis session security store with parent-child token lineage tracking to revoke entire compromised tree on replay. | LOW | API Security |
| **RSK-MOB-07** | **FlutterSecureStorage Corrupt KeyStore Exception** (`MOB-STORAGE-02`): Default storage constructor lacks `resetOnError: true` on Android. | MEDIUM | MEDIUM | **MEDIUM** | Pass `AndroidOptions(encryptedSharedPreferences: true, resetOnError: true)` in `FlutterSecureSessionStorage`. | LOW | Mobile Core |

---

## Risk Treatment & Governance Plan

1. **Immediate Release Gate:** Incorporate `scripts/ops/audit_mobile_auth_session_security.py` into automated CI check to prevent regression of token filters and backup attributes.
2. **Phase Handoff:** Pass actionable remediation tasks for `RSK-MOB-01`, `RSK-MOB-02`, and `RSK-MOB-03` to Mobile Core and API subagents for implementation in follow-up sprint.
3. **Zero-PII Assurance:** Confirmed no personal health information (PHI) or authentication secrets are logged or captured by existing mobile analytics infrastructure.
