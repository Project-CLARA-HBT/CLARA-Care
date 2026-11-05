# Wearable & Connected Health Data Retention & Privacy Assessment

**Document Status:** Sealed Compliance Architecture & Data Protection Impact Assessment (DPIA) · Subagent PH13_A08  
**Repository Branch:** `phase/ph13-a08`  
**Base Commit SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`  
**Regulatory Standards:** Vietnam Decree 13/2023/ND-CP, GDPR (Art. 6, 9, 17, 35), HIPAA Security & Privacy Rules, Google Play Health Apps Declaration Policy, Huawei Health Kit Developer Agreement.  
**Review Owner:** Security + Privacy Subagent (PH13 / A08)  
**Date:** November 2026  
**Scope:** Telemetry Ingestion, Consent Lifecycle, Retention & Deletion Cascades, OAuth Credential Vaulting, and Cross-Border Considerations.

---

## 1. Regulatory Context & Compliance Mandates

Connecting wearable devices (smartwatches, fitness trackers, smart scales, continuous monitors) to CLARA introduces sensitive personal health data under Vietnamese and international privacy laws. Under **Vietnam Decree 13/2023/ND-CP (Điều 2, Khoản 4)**, health data is explicitly classified as **Sensitive Personal Data (Dữ liệu cá nhân nhạy cảm)**, triggering stringent requirements:

1. **Explicit Prior Consent (Sự đồng ý rõ ràng):** The data subject must give affirmative, unambiguous consent for each specific processing purpose and data category before data collection commences.
2. **Right to Withdraw Consent & Request Deletion (Quyền rút lại sự đồng ý & Quyền xóa dữ liệu):** Users must be empowered to disconnect connectors and request complete deletion of imported records at any time.
3. **Data Minimization (Hạn chế thu thập):** Only biometric metrics directly serving the user's active health goals may be collected. Speculative collection is strictly prohibited.
4. **Impact Assessment (Đánh giá tác động xử lý dữ liệu cá nhân - DPIA):** The processing of sensitive health data must be formally evaluated for technical, operational, and clinical risks.

---

## 2. Granular Consent Architecture

CLARA treats wearable integration consent as an isolated, versioned contract separate from general Terms of Service or clinical AI consent.

### 2.1 Consent Entity Specification (`ConnectorConsent`)
- **Version Tracking:** Every consent grant records `consent_version` (e.g. `"1.0"`).
- **Purpose Binding:** Purposes are explicitly chosen by the user (`purposes_json` array):
  - `personal_health_assistance`: Baseline visualization and wellness recommendations.
  - `clinical_consultation`: Sharing wearable summaries with licensed doctors during consultations.
  - `research_contribution`: De-identified population health analytics (requires separate explicit opt-in).
- **Data-Type Scoping:** Granular permissions are restricted to user-approved metrics (`data_types_json`):
  - Common: `steps`, `activity`, `sleep`, `heart_rate`, `resting_heart_rate`.
  - Clinical: `blood_pressure`, `oxygen_saturation`, `blood_glucose`, `body_temperature`.
- **Directionality:** Access direction is hard-locked to `"read"` in current releases. Bidirectional writing back to vendor platforms is disabled.

### 2.2 Revocation Immediacy
When a user disconnects a connector or toggles off a permission:
1. `ConnectorConsent.revoked_at` is stamped with the server's UTC time.
2. The connector transitions to status `"disconnected"`.
3. Ingestion attempts immediately fail with HTTP 403 Forbidden (`detail="Connector consent revoked"`).
4. No background worker or scheduled sync may execute for a revoked connector.

---

## 3. Data Retention Lifecycle & Deletion Cascades

CLARA implements a rigorous tiered retention schedule to balance patient longitudinal continuity against data minimization principles:

| Data Category | Storage Location | Retention Period | Deletion Trigger / Lifecycle |
|---|---|---|---|
| **Raw Ingest Transport Payloads** | In-flight HTTP request | **0 seconds (Ephemeral)** | Payloads are validated in memory. Only the SHA-256 hash (`payload_hash`) is persisted; raw JSON payloads are immediately dropped. |
| **OAuth Credentials & Tokens** | `ConnectorAccount.token_ciphertext` (AES-256-GCM) | **Until disconnect / reauth** | Completely purged (`NULL`) immediately upon connector disconnection or consent revocation. |
| **OAuth State & PKCE Verifiers** | `ConnectorOAuthTransaction` | **15 minutes** | Short-lived transaction window; swept by automated cleanup after `expires_at`. |
| **Active Wearable Observations** | `WearableObservations` | **User-directed / 10 years** | Retained while connected; deleted upon user invocation of `DELETE /{id}/imported-data`. |
| **Prior Observation Versions** | `WearableObservationVersions` | **Audit retention (10 years)** | Created on record modification or tombstone; deleted when parent observation is deleted. |
| **Derived Daily Aggregates** | `WearableDailyAggregates` | **Tied to source records** | Atomically deleted/invalidated when contributing observations are removed. |
| **Connector Audit Events** | `ConnectorAuditEvents` | **10 years (Statutory)** | Minimum-metadata log (actor, timestamp, event type, counts); contains zero PHI or credentials. |

### 3.1 Cascading Deletion Mechanism (`delete_imported_data`)
When a user requests imported data deletion (`DELETE /api/v1/connectors/{id}/imported-data`):
1. **Source Discovery:** All `WearableObservation` records matching `connector_id` are identified.
2. **Dependent Projection Identification:** All `WearableAggregateContribution` links are traced to identify affected `WearableDailyAggregate` IDs.
3. **Atomic Purge:**
   - Observations and observation versions are deleted via `ON DELETE CASCADE`.
   - All dependent daily aggregates are deleted to prevent corrupted or ghost averages.
4. **Audit Ledgering:** A `ConnectorAuditEvent` of type `"connector.imported_data_deleted"` is written, recording the exact count of deleted observations and invalidated aggregates.
5. **Response Assurance:** The API returns `ImportedDataDeletionResponse(deleted_observations=N, invalidated_aggregates=M)`.

---

## 4. Platform-Specific Privacy Declarations

### 4.1 Android Health Connect & Google Play Health Apps Declaration
- **Read-Only Minimal Scopes:** CLARA requests only runtime permissions matching user-selected goals.
- **Privacy Policy Parity:** The privacy policy presented in the Google Play Data Safety form matches the exact in-app disclosure presented in the mobile getting-started screen.
- **No Background Polling:** Data sync occurs opportunistically on application open or via bounded WorkManager jobs conforming to Google Play battery and background execution guidelines.

### 4.2 Huawei Health Kit Developer Compliance
- **Flavor Isolation:** Huawei HMS dependencies are compiled within flavor-guarded boundaries so non-Huawei devices execute zero HMS code.
- **No Cross-Border Telemetry:** Health observations processed from Vietnamese patients stay strictly within CLARA's regional data residency infrastructure.

### 4.3 Fitbit Cloud OAuth Integration
- **Server-Side Token Vault:** The mobile client NEVER receives Fitbit client secrets or direct refresh tokens.
- **PKCE Enforcement:** OAuth authorization flows enforce PKCE verification to protect against authorization code interception.

---

## 5. Telemetry & Log Sanitization Invariants

To comply with Decree 13/2023/ND-CP and CLARA core architecture mandates:
1. **Zero PII in Logs:** Patient names, email addresses, phone numbers, and physical addresses are strictly excluded from logging.
2. **Zero PHI in Logs:** Physiological metrics (heart rates, step counts, blood glucose readings, blood pressure values) are excluded from server stdout/stderr and error reporting.
3. **Zero Secrets in Logs:** Authorization headers, Bearer tokens, OAuth codes, and PKCE verifiers are filtered before logging.
4. **Audit Metadata Bounds:** Audit event metadata is limited to operational counters:
   ```json
   {
     "accepted_count": 12,
     "upserted_count": 12,
     "tombstoned_count": 0
   }
   ```
