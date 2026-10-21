# Mobile Flutter & Compose Risk Register (PH01_A06)

## 1. Overview & Risk Scoring Matrix

- **Subagent**: `A06`
- **Phase**: `PH01`
- **Role**: `Mobile Flutter`
- **Path Lane**: `apps/mobile/`, `deploy/`, `artifacts/PH01/A06/`
- **Frozen HEAD SHA**: `2aa9016a57b49b53f1a433d076e1028a6ec45f64`

| Risk ID | Title | Severity | Likelihood | Impact | Status |
|---|---|---|---|---|---|
| `RISK-PH01-MOB-01` | Host Port 5432 Collision with Pre-existing PostgreSQL Containers | High | High | High | Mitigated via Config |
| `RISK-PH01-MOB-02` | Local Toolchain SDK Mismatch (Dart 3.7.0 vs. markdown ^3.9.0) | High | High | High | Open / Documented |
| `RISK-PH01-MOB-03` | Android Cleartext HTTP Blockage in Debug Builds on API 28+ | Medium | High | High | Mitigated via Debug Overlay |
| `RISK-PH01-MOB-04` | iOS Native Project Scaffold Absent from Source Control | High | High | High | Accepted / Documented |
| `RISK-PH01-MOB-05` | Indiscriminate Compose Up of Heavy Infra (Milvus, Elastic, Neo4j) | High | Medium | High | Mitigated by Start Script |
| `RISK-PH01-MOB-06` | Android App Links Verification Dependent on Production Key Fingerprint | Medium | High | Medium | Monitored |

---

## 2. Detailed Risk Profiles

### RISK-PH01-MOB-01: Host Port 5432 Collision with Pre-existing PostgreSQL Containers
- **Description**: The host workstation frequently has development database containers running on host port 5432 (such as `luuniensuki-lms-db-1` on `127.0.0.1:5432`). Running `docker compose up postgres` without specifying `POSTGRES_PORT` results in `bind: address already in use` error.
- **Source Anchor**: `deploy/docker/docker-compose.yml:19` (`ports: - "${POSTGRES_PORT:-5432}:5432"`).
- **Impact**: Developer or CI failure when starting the CLARA local stack if 5432 is occupied.
- **Remediation**:
  1. Default port is parameterized with `${POSTGRES_PORT:-5432}`.
  2. Developers with port conflicts can set `POSTGRES_PORT=54329` in their local `.env`.
  3. Validated during smoke test that overriding `POSTGRES_PORT=54329` binds and functions without port collision.

---

### RISK-PH01-MOB-02: Local Toolchain SDK Mismatch (Dart 3.7.0 vs. markdown ^3.9.0)
- **Description**: The committed `pubspec.lock` contains `markdown: 7.3.1`, which specifies a Dart SDK constraint of `^3.9.0`. The host workstation environment provides Flutter 3.29.0 with Dart 3.7.0 (`/home/clue/development/flutter`). Running `flutter pub get` or `flutter test` fails during dependency resolution (`markdown ^7.3.1 is forbidden`).
- **Source Anchor**: `apps/mobile/pubspec.lock:368-375`, `apps/mobile/pubspec.yaml:16`.
- **Impact**: Developers working directly on this host without containerization cannot execute local `flutter test` or `flutter run` invocations.
- **Remediation**:
  1. Upgrade host Flutter SDK to `>=3.47.7` (Dart `>=3.9.0`).
  2. Execute mobile test suites inside a standardized Docker container mirroring CI toolchains.
  3. CI pipeline (`.github/workflows/`) pins `setup-flutter` to compatible `>=3.47.7` versions.

---

### RISK-PH01-MOB-03: Android Cleartext HTTP Blockage in Debug Builds on API 28+
- **Description**: Android 9+ (API 28+) disables cleartext HTTP by default. When developers build and run debug builds targeting local endpoints (`http://localhost:8100` via `adb reverse` or `http://10.0.2.2:8100` on emulator), network calls are rejected by the Android OS with `Cleartext HTTP traffic not permitted`.
- **Source Anchor**: `apps/mobile/android/app/src/debug/AndroidManifest.xml:1-8`.
- **Impact**: Inability to develop or debug mobile against local API services without configuring TLS certificates on local machines.
- **Remediation**:
  1. Added `<application android:usesCleartextTraffic="true"/>` strictly to `apps/mobile/android/app/src/debug/AndroidManifest.xml`.
  2. Release manifest (`src/main/AndroidManifest.xml`) does NOT have this flag, ensuring production release APKs enforce strict HTTPS only.

---

### RISK-PH01-MOB-04: iOS Native Project Scaffold Absent from Source Control
- **Description**: Directory `apps/mobile/ios/` does not exist in the repository. While `apps/mobile/android/` contains complete build configurations (Gradle 9.1.0, Kotlin 2.3.20, AndroidManifest, Proguard/R8, App Links, release keystore bindings), iOS has no committed Xcode workspace, scheme, or plist configurations.
- **Source Anchor**: `apps/mobile/` root directory; `apps/mobile/README.md:261-265`.
- **Impact**: iOS compilation cannot be performed in CI or local macOS environments without manually running `flutter create . --platforms=ios`. Critical iOS configurations (Microphone permissions for Scribe, Camera permissions for Cabinet OCR, Associated Domains for Universal Links) would have to be manually re-applied each time unless committed.
- **Remediation**:
  1. Scaffold `apps/mobile/ios/` with `com.theclaracare.app` bundle ID and commit the platform runner files.
  2. Add `NSMicrophoneUsageDescription` and `NSCameraUsageDescription` to `ios/Runner/Info.plist`.
  3. Add `applinks:theclaracare.com` and `applinks:www.theclaracare.com` to `Runner.entitlements`.

---

### RISK-PH01-MOB-05: Indiscriminate Compose Up of Heavy Infra (Milvus, Elastic, Neo4j)
- **Description**: `deploy/docker/docker-compose.yml` defines Milvus (with etcd and MinIO), Elasticsearch, and Neo4j alongside PostgreSQL and Redis. Running `docker compose up -d` without specifying service names attempts to launch all 7 infrastructure services, consuming >6GB of RAM.
- **Source Anchor**: `deploy/docker/docker-compose.yml:45-129`, `scripts/start-clara.sh:50-52`.
- **Impact**: Potential OOM kills or system freezing on development workstations with limited RAM (e.g. <=8GB).
- **Remediation**:
  1. `scripts/start-clara.sh` explicitly executes `docker compose -f docker-compose.yml up -d postgres redis`, deliberately omitting the heavy vector/graph databases until those specific backends are activated in application configuration.
  2. Documented in runbooks and startup guides.

---

### RISK-PH01-MOB-06: Android App Links Verification Dependent on Production Key Fingerprint
- **Description**: `apps/mobile/android/app/src/main/AndroidManifest.xml:30-47` declares intent filters with `android:autoVerify="true"` for `https://theclaracare.com/phr/shared/*` and `https://www.theclaracare.com/phr/shared/*`. Android 12+ strictly enforces Digital Asset Links verification. If the deployed `/.well-known/assetlinks.json` does not contain the exact SHA-256 fingerprint of the APK signing key, Android fails verification silently and falls back to opening links in a web browser.
- **Source Anchor**: `apps/mobile/android/app/src/main/AndroidManifest.xml:30-47`, `apps/mobile/README.md:219-232`.
- **Impact**: Deep links shared between patients and doctors would open in the web browser instead of triggering the native `SharedResourceScreen`.
- **Remediation**:
  1. Ensure web deployment sets `ANDROID_APP_LINK_CERT_SHA256` matching the production keystore alias `claracare`.
  2. Confirm `GET /.well-known/assetlinks.json` returns valid JSON with `delegate_permission/common.handle_all_urls`.
