# Connected Health & Wearables: Vendor Sandbox Test Instructions & Integration Runbook

Owner: Clinical Safety, Mobile Platform Engineering & Quality Engineering  
Target Audience: Mobile Engineers, Backend Integrators, QA Automation Engineers, SREs, and Security Auditors  
Classification: Operational Runbook & Vendor Testing Standard  
Phase: PH13 — Connected Health và wearables  

---

## 1. Architectural Overview & Security Invariants

CLARA Care integrates personal health metrics from smart wearables and native operating system health databases into the personal health record (PHR) and LifeMap longitudinal intelligence timeline. CLARA is a **clinical assistant, not an autonomous doctor replacement**; wearable data constitutes **supplemental patient-generated health data (PGHD)**, not authoritative clinical diagnostic truth.

### Core Architectural Invariants
1. **Zero-Mock Staging Isolation:**
   - Synthetic test data generated in vendor sandboxes must be strictly confined to synthetic staging profiles (`is_synthetic = True` or isolated staging database).
   - Mock data generated via sandbox tools (e.g., Health Connect Toolbox, simulator injections) must NEVER be commingled with real patient clinical records.
2. **Statutory Consent Gate:**
   - No health data may be read from or written to an external provider without explicit, versioned, purpose-bound user consent (`ConnectorConsent`).
   - Revoking consent immediately terminates active synchronization, invalidates access tokens, and blocks new batch imports with HTTP `403 Forbidden`.
3. **Idempotency & Replay Resistance:**
   - Every batch import requires an explicit `idempotency_key` and cryptographic payload hash (`sha256:...`). Replaying an identical batch yields an idempotent cached response without duplicate database insertions or aggregate re-inflation.
   - Replaying an existing key with altered data triggers HTTP `409 Conflict`.
4. **Interval Deduplication (No Multi-Device Double Counting):**
   - When multiple devices or sources report overlapping activity intervals (e.g., smart watch and smartphone both counting steps simultaneously), CLARA's aggregate projector selects the primary origin by duration coverage and max non-overlapping interval value. Step counts are never blindly summed across overlapping intervals.
5. **Physiological Boundary Validation:**
   - All inbound values must fall within human physiological bounds (e.g., Heart Rate $0 \le \text{bpm} \le 300$, Weight $0 < \text{kg} \le 1000$, Blood Pressure systolic/diastolic $0 < \text{mmHg} \le 400$). Infinite or NaN values are rejected at the schema validator.
6. **Zero-PII Telemetry:**
   - Vendor OAuth tokens, refresh tokens, device identifiers, and raw biometric records are strictly excluded from Sentry, Prometheus labels, and application logs.

---

## 2. Google Health Connect Sandbox & Testing

### 2.1 Overview & Architecture
Google Health Connect serves as the central on-device repository for Android devices. On Android 14+ (API 34+), Health Connect is a core Android system service. On Android 9 to 13 (API 28–33), it operates as a standalone APK (`com.google.android.apps.healthdata`).

CLARA communicates with Health Connect via a first-party Kotlin bridge integrated into `apps/mobile/android`.

### 2.2 Prerequisites & Setup
1. **Test Devices / Emulators:**
   - Physical Android device running Android 9+ with Google Play Services, OR
   - Android Emulator running Android 14 (API 34) Google APIs system image.
2. **Install Health Connect & Toolbox:**
   - For Android < 14: Install Health Connect APK from Google Play Store or sideload `com.google.android.apps.healthdata`.
   - Install **Health Connect Toolbox** (`com.google.android.apps.healthdata.toolbox`) from the Play Store or GitHub releases. The Toolbox allows manual injection of synthetic records (Steps, Heart Rate, Sleep, Blood Glucose, SpO2) without needing physical fitness hardware.
3. **App Manifest Configuration (`apps/mobile/android/app/src/main/AndroidManifest.xml`):**
   ```xml
   <!-- Health Connect Intent Filter for Privacy Policy -->
   <activity-alias
       android:name="ViewPermissionUsageActivity"
       android:targetActivity=".MainActivity"
       android:permission="android.permission.START_VIEW_PERMISSION_USAGE"
       android:exported="true">
       <intent-filter>
           <action android:name="android.intent.action.VIEW_PERMISSION_USAGE" />
           <category android:name="android.intent.category.HEALTH_PERMISSIONS" />
       </intent-filter>
   </activity-alias>

   <!-- Declared Read Permissions -->
   <uses-permission android:name="android.permission.health.READ_STEPS"/>
   <uses-permission android:name="android.permission.health.READ_HEART_RATE"/>
   <uses-permission android:name="android.permission.health.READ_RESTING_HEART_RATE"/>
   <uses-permission android:name="android.permission.health.READ_SLEEP"/>
   <uses-permission android:name="android.permission.health.READ_OXYGEN_SATURATION"/>
   <uses-permission android:name="android.permission.health.READ_BLOOD_PRESSURE"/>
   ```

### 2.3 Step-by-Step Testing Procedure

#### Step 1: Health Connect Availability Check
Execute capability check on device:
```dart
final status = await HealthSourceCapabilityService.checkHealthConnectAvailability();
// Expect: HealthConnectAvailability.installed
```
If not installed, verify that the application presents a non-coercive "Install Health Connect" button opening Google Play Store.

#### Step 2: Permission Authorization Flow
1. Navigate to Settings -> Connected Health (`/experience/connected_health`).
2. Select **Google Health Connect** and toggle "Cho phép đồng bộ".
3. Verify that the Android system Health Connect permission dialog appears requesting ONLY the declared read permissions.
4. Test Partial Grant:
   - Allow "Số bước" (Steps), but Deny "Nhịp tim" (Heart Rate).
   - Verify CLARA registers connector with `data_types: ["steps"]` only.
   - Verify backend enforces scope filtering: any attempt to import heart rate records yields HTTP `403 Forbidden` (`detail: "Import includes unconsented data type"`).

#### Step 3: Injecting Synthetic Data via Health Connect Toolbox
1. Open **Health Connect Toolbox** on the test device.
2. Insert Test Record A:
   - Type: `Steps`
   - Count: `3500`
   - Time: Today, 08:00 to 09:00 local time
   - Origin: `com.google.android.apps.healthdata.toolbox`
3. Insert Test Record B (Overlapping interval to test deduplication):
   - Type: `Steps`
   - Count: `4200`
   - Time: Today, 08:15 to 09:15 local time (overlapping by 45 mins)
   - Origin: `com.sec.android.app.shealth`
4. Trigger synchronization in CLARA mobile app: "Đồng bộ ngay".

#### Step 4: Verification in API & Database
Verify the imported batch response:
```bash
# Check connector batch state
curl -s -H "Authorization: Bearer $TEST_TOKEN" \
  http://localhost:8000/api/v1/connectors | jq .
```
Verify aggregate deduplication:
```sql
SELECT local_date, record_type, value_json, primary_origin, policy_version 
FROM wearable_daily_aggregates 
WHERE profile_id = :test_profile_id;
```
**Acceptance Criterion:** The aggregate step count selects the winner of the overlapping interval (never summing $3500 + 4200 = 7700$). The daily aggregate reflects proper max coverage.

#### Step 5: Tombstone & Deletion Verification
1. In Health Connect Toolbox, delete the steps record from 08:00 to 09:00.
2. Trigger sync.
3. Verify mobile sends `ConnectorRecordTombstone` with `deleted_at`.
4. Inspect `wearable_observations`: record is marked `is_active = false`, version incremented in `wearable_observation_versions`, and daily aggregate recomputed.

---

## 3. Apple HealthKit Bridge Sandbox & Testing

### 3.1 Overview & Architecture
Apple HealthKit provides central health data management on iOS. Access requires explicit entitlement (`com.apple.developer.healthkit`), declared usage descriptions in `Info.plist`, and runtime user authorization via `HKHealthStore`.

CLARA connects via an iOS Native Swift Bridge exposing unified MethodChannels to Flutter.

### 3.2 Prerequisites & Setup
1. **Apple Developer Account & Provisioning:**
   - App ID configured with HealthKit capability enabled.
   - Entitlements file (`apps/mobile/ios/Runner/Runner.entitlements`):
     ```xml
     <dict>
         <key>com.apple.developer.healthkit</key>
         <true/>
         <key>com.apple.developer.healthkit.access</key>
         <array/>
     </dict>
     ```
2. **Info.plist Privacy Declarations (`apps/mobile/ios/Runner/Info.plist`):**
   ```xml
   <key>NSHealthShareUsageDescription</key>
   <string>CLARA cần quyền đọc dữ liệu bước chân, giấc ngủ và nhịp tim để hỗ trợ bạn theo dõi xu hướng sức khỏe cá nhân trong LifeMap.</string>
   <key>NSHealthUpdateUsageDescription</key>
   <string>CLARA không ghi đè dữ liệu sức khỏe của bạn.</string>
   ```
3. **iOS Simulator Testing:**
   - Launch iOS Simulator (iPhone 15 / 16, iOS 17+).
   - Apple Simulator includes a functional **Health app** (`Apple Health`).

### 3.3 Step-by-Step Testing Procedure

#### Step 1: Simulator Health Data Simulation
1. Open the **Health** app inside the iOS Simulator.
2. Select **Browse** -> **Activity** -> **Steps**.
3. Tap **Add Data** in top-right corner:
   - Date: Today, 07:00 AM
   - Steps: `5420`
4. Browse to **Vitals** -> **Heart Rate**:
   - Add sample: `72 bpm` at 07:30 AM.
5. Browse to **Sleep** -> **Add Data**:
   - Sleep interval: Yesterday 23:00 to Today 06:30 (Asleep).

#### Step 2: Authorization Handling & Privacy Blindness
1. Launch CLARA in iOS Simulator.
2. Open Connected Health -> Select **Apple HealthKit**.
3. Tap "Kết nối Apple Health".
4. System modal appears. Authorize "Steps" and "Heart Rate".
5. **Security Invariant Verification (Apple Privacy Blindness):**
   - Note: HealthKit authorization status for read access is intentionally obscured by iOS (`HKAuthorizationStatus.sharingDenied` is indistinguishable from user declining read permissions for privacy reasons).
   - Verify CLARA handles empty sample queries gracefully without displaying error alerts or accusing the user of denial.

#### Step 3: Incremental Sync via `HKAnchoredObjectQuery`
1. CLARA iOS bridge executes `HKAnchoredObjectQuery` using stored anchor tokens.
2. Extracted samples are serialized into CLARA's `CanonicalHealthRecord` format:
   ```json
   {
     "schema_version": "1.0",
     "profile_id": "prof_123",
     "connector_id": "conn_456",
     "provider": "health_connect",
     "provider_record_id": "HKQuantitySample_UUID_A1B2C3",
     "record_type": "steps",
     "value": {"scalar": 5420.0, "unit": "count"},
     "observed_start": "2026-10-24T00:00:00Z",
     "observed_end": "2026-10-24T01:00:00Z",
     "zone_offset_start": "+07:00",
     "zone_offset_end": "+07:00",
     "data_origin": "com.apple.Health",
     "device": {"manufacturer": "Apple", "model": "iPhone", "type": "phone"},
     "recording_method": "automatic",
     "provenance": {
       "adapter_version": "1.0-ios",
       "raw_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
     }
   }
   ```
3. Deliver batch to `POST /api/v1/connectors/{id}/imports`.
4. Verify response HTTP `200 OK` with `accepted_count = 1, upserted_count = 1`.

#### Step 4: Background Delivery Verification
1. In Xcode, simulate background fetch: `Debug -> Simulate Background Fetch`.
2. Ensure `enableBackgroundDelivery(for:frequency:)` wakes the app without crashing and schedules an incremental sync batch.

---

## 4. Fitbit Web API Sandbox & Testing

### 4.1 Overview & Architecture
Fitbit operates via cloud-to-cloud server synchronization using OAuth 2.0 with PKCE. Tokens are stored encrypted in the backend database (`connector_accounts.token_ciphertext`).

### 4.2 Prerequisites & Setup
1. **Fitbit Developer Account Registration:**
   - Log in to `dev.fitbit.com` using test Google/Fitbit account.
   - Register Application:
     - Application Name: `CLARA Care Sandbox`
     - OAuth 2.0 Application Type: `Personal` (or `Server` for staging)
     - Callback URL: `https://staging-api.theclaracare.com/api/v1/connectors/fitbit/callback` (or `http://localhost:8000/api/v1/connectors/fitbit/callback`)
     - Default Access Type: `Read-Only`
2. **Environment Configuration (`services/api/.env`):**
   ```bash
   FITBIT_CLIENT_ID=23TESTX
   FITBIT_CLIENT_SECRET=sandbox_secret_abcdef1234567890
   FITBIT_REDIRECT_URI=http://localhost:8000/api/v1/connectors/fitbit/callback
   FITBIT_WEBHOOK_VERIFICATION_CODE=sandbox_verify_token_999
   ```
3. **Approved Scopes:**
   - `activity`: Steps, distance, active minutes
   - `heartrate`: Continuous heart rate & resting heart rate
   - `sleep`: Sleep stages and duration
   - `oxygen_saturation`: SpO2 daily summary
   - `weight`: Body weight and BMI

### 4.3 Step-by-Step Testing Procedure

#### Step 1: Initiating OAuth Flow with PKCE
1. Client initiates authorization:
   `POST /api/v1/connectors/fitbit/authorize`
2. Backend generates cryptographically random `code_verifier`, derives `code_challenge = SHA256(code_verifier)`, and signs HMAC `state` token encoding `user_id` and `profile_id`.
3. Browser is directed to Fitbit consent page:
   ```text
   https://www.fitbit.com/oauth2/authorize?response_type=code
     &client_id=23TESTX
     &scope=activity%20heartrate%20sleep%20oxygen_saturation%20weight
     &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSipt-AE
     &code_challenge_method=S256
     &state=signed_state_token
   ```

#### Step 2: Callback Exchange & Token Vaulting
1. User approves scopes. Fitbit redirects to callback URL with authorization code.
2. Callback endpoint exchanges code for token pair:
   - `access_token` (valid 8 hours)
   - `refresh_token` (valid 28 days)
3. **Security Invariant Verification:**
   - Verify `token_ciphertext` is encrypted using AES-256-GCM before writing to `connector_accounts`.
   - Verify raw token never appears in application logs or Sentry breadcrumbs.

#### Step 3: Webhook Subscription & Verification
1. Setup Fitbit Subscriber endpoint:
   `GET /api/v1/connectors/fitbit/webhook`
2. Verify Fitbit endpoint verification check returns HTTP `204 No Content` when `verify` query parameter matches `FITBIT_WEBHOOK_VERIFICATION_CODE`.
3. Simulate inbound webhook notification:
   ```json
   [
     {
       "collectionType": "activities",
       "date": "2026-10-24",
       "ownerId": "FITBIT_USER_123",
       "ownerType": "user",
       "subscriptionId": "sub_456"
     }
   ]
   ```
4. Verify backend enqueues asynchronous sync worker job without processing heavy sync inside the webhook request thread.

#### Step 4: Rate Limit & 429 Handling
Fitbit enforces a limit of **150 API requests per hour per user**.
1. Test rate limit response:
   - Mock response from Fitbit API returning HTTP `429 Too Many Requests` with `Retry-After: 3600`.
   - Verify sync worker detects 429, sets connector status to `rate_limited`, logs backoff metric, and reschedules job after the specified retry interval.
   - Verify no repeated retries hammer the vendor endpoint.

#### Step 5: Refresh Token Rotation
1. Simulate access token expiry (pass expired token or simulate 401 Unauthorized from vendor).
2. Sync worker calls `https://api.fitbit.com/oauth2/token` with `grant_type=refresh_token`.
3. New token pair returned; old refresh token is discarded and new token encrypted in DB.

---

## 5. Troubleshooting & Diagnostics

| Symptom / Error | Root Cause | Remediation Procedure |
|---|---|---|
| `403 Forbidden: Import scope mismatch` | `payload.connector_id` or `payload.profile_id` does not match authenticated connector record | Ensure client uses connector ID returned by `POST /connectors/device`. Do not hardcode connector IDs across test sessions. |
| `403 Forbidden: Import includes unconsented data type` | Client submitted record type (e.g. `blood_glucose`) not granted in `ConnectorConsent.data_types_json` | Check connector consent scopes; prompt user to grant permission or filter records device-side prior to sync batch. |
| `409 Conflict: Idempotency key was already used for another payload` | Client reused `idempotency_key` with modified record data or different count | Ensure each new distinct sync payload generates a fresh UUIDv4 `idempotency_key`. Replay identical keys only for network retry. |
| `409 Conflict: Connector is not available for imports` | Connector is in `paused`, `disconnected`, or `error` state | Resume connector via `POST /connectors/{id}/resume` or reauthorize before attempting imports. |
| `422 Unprocessable Entity: measurement values must be finite` | Biometric value contained `NaN`, `Infinity`, or negative steps | Sanitize sensor values device-side; discard non-finite floating point records before JSON serialization. |
| `Fitbit OAuth 400: Invalid State` | State token expired or tampered | State tokens expire in 10 minutes. Initiate fresh OAuth flow from client. |

---

## 6. Audit & Acceptance Checklist

Prior to approving Connected Health integrations for staging or production:
- [x] All 3 vendor bridges tested with synthetic sandbox tools.
- [x] Zero mock or synthetic records committed to production databases.
- [x] Overlapping step count intervals choose max/coverage rather than summing.
- [x] Revoking consent immediately denies batch imports with HTTP 403.
- [x] Idempotent batch replay verified; payload tampering detected with HTTP 409.
- [x] Rate limiting (Fitbit 150 req/hr) and 429 backoff implemented.
- [x] All tokens vaulted with AES-256-GCM encryption; zero secrets in logs.
- [x] Verified path ACL conformance with Phase PH13 lane restrictions.
