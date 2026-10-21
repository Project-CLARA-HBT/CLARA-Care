# Mobile Flutter Risk Register (PH00_A06)

## 1. Overview & Risk Scoring Matrix

- **Subagent**: `A06`
- **Phase**: `PH00`
- **Role**: `Mobile Flutter`
- **Path Lane**: `apps/mobile/`, `artifacts/PH00/A06/`
- **Frozen HEAD SHA**: `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`

| Risk ID | Title | Severity | Likelihood | Impact | Status |
|---|---|---|---|---|---|
| `RISK-MOB-01` | Local Toolchain SDK Mismatch (Dart 3.7.0 vs. markdown ^3.9.0) | High | High | High | Open |
| `RISK-MOB-02` | iOS Native Project Scaffold Absent in Version Control | High | High | High | Open |
| `RISK-MOB-03` | Android App Links Verification Dependent on Release Key Fingerprint | Medium | High | Medium | Monitored |
| `RISK-MOB-04` | Scribe Audio Encounter In-Memory Buffering (OOM Risk on Low RAM) | Medium | Medium | Medium | Open |
| `RISK-MOB-05` | Administrative Backoffice Features Web-Only | Low | Low | Low | Accepted |
| `RISK-MOB-06` | Strict Offline Mutation Blocking Without Asynchronous Outbox | Low | Medium | Low | Accepted by Design |

---

## 2. Detailed Risk Profiles

### RISK-MOB-01: Local Toolchain SDK Mismatch (Dart 3.7.0 vs. markdown ^3.9.0)
- **Description**: The committed `pubspec.lock` locks `markdown` at version `7.3.1`, which specifies a Dart SDK constraint of `^3.9.0`. The host workstation environment provides Flutter 3.29.0 with Dart 3.7.0 (`/home/clue/development/flutter`). Running `flutter pub get` or `flutter test` fails during dependency resolution (`markdown ^7.3.1 is forbidden`).
- **Source Anchor**: `apps/mobile/pubspec.lock:368-375`, `apps/mobile/pubspec.yaml:16`.
- **Impact**: Developers working directly on this host without containerization cannot execute local `flutter test` or `flutter run` invocations.
- **Remediation / Workaround**:
  1. Upgrade host Flutter SDK to `>=3.47.7` (Dart `>=3.9.0`).
  2. Execute mobile test suites inside a standardized Docker container mirroring CI toolchains.
  3. CI pipeline (`.github/workflows/`) must pin `setup-flutter` to compatible `>=3.47.7` versions.

---

### RISK-MOB-02: iOS Native Project Scaffold Absent in Version Control
- **Description**: Directory `apps/mobile/ios/` does not exist in the repository. While `apps/mobile/android/` contains complete build configurations (Gradle 9.1.0, Kotlin 2.3.20, AndroidManifest, Proguard/R8, App Links, release keystore bindings), iOS has no committed Xcode workspace, scheme, or plist configurations.
- **Source Anchor**: `apps/mobile/` root directory; `apps/mobile/README.md:261-265`.
- **Impact**: iOS compilation cannot be performed in CI or local macOS environments without manually running `flutter create . --platforms=ios`. Critical iOS configurations (Microphone permissions for Scribe, Camera permissions for Cabinet OCR, Associated Domains for Universal Links) would have to be manually re-applied each time unless committed.
- **Remediation / Workaround**:
  1. Scaffold `apps/mobile/ios/` with `com.theclaracare.app` bundle ID and commit the platform runner files.
  2. Add `NSMicrophoneUsageDescription` and `NSCameraUsageDescription` to `ios/Runner/Info.plist`.
  3. Add `applinks:theclaracare.com` and `applinks:www.theclaracare.com` to `Runner.entitlements`.

---

### RISK-MOB-03: Android App Links Verification Dependent on Release Key Fingerprint
- **Description**: `apps/mobile/android/app/src/main/AndroidManifest.xml:30-47` declares intent filters with `android:autoVerify="true"` for `https://theclaracare.com/phr/shared/*` and `https://www.theclaracare.com/phr/shared/*`. Android 12+ strictly enforces Digital Asset Links verification. If the deployed `/.well-known/assetlinks.json` does not contain the exact SHA-256 fingerprint of the APK signing key, Android fails verification silently and falls back to opening links in a web browser.
- **Source Anchor**: `apps/mobile/android/app/src/main/AndroidManifest.xml:30-47`, `apps/mobile/README.md:219-232`.
- **Impact**: Deep links shared between patients and doctors would open in the web browser instead of triggering the native `SharedResourceScreen`.
- **Remediation / Workaround**:
  1. Ensure web deployment sets `ANDROID_APP_LINK_CERT_SHA256` matching the production keystore alias `claracare`.
  2. Confirm `GET /.well-known/assetlinks.json` returns valid JSON with `delegate_permission/common.handle_all_urls`.

---

### RISK-MOB-04: Scribe Audio Encounter In-Memory Buffering (OOM Risk on Low RAM)
- **Description**: During ambient clinical scribe sessions (`ScribeSurfaceV3`), recorded PCM/WAV audio data is accumulated in memory before being packaged into a multipart request for `POST /api/v1/scribe/transcribe`. On entry-level Android devices (e.g., devices with <=3GB RAM), consultations exceeding 20-30 minutes can create multi-megabyte raw audio arrays that could trigger OutOfMemory crashes.
- **Source Anchor**: `apps/mobile/lib/experience/redesign/scribe_surface_v3.dart:180-240`, `apps/mobile/lib/core/api_client.dart:1421`.
- **Impact**: App crash during clinical consultation recording, causing potential loss of uncommitted clinical encounter notes.
- **Remediation / Workaround**:
  1. Enforce max recording chunk durations (e.g., 10-minute intervals).
  2. Stream audio chunks directly to local temporary storage (`getTemporaryDirectory`) rather than accumulating in RAM.

---

### RISK-MOB-05: Administrative Backoffice Features Web-Only
- **Description**: Complex backoffice operations (`/admin/knowledge-sources`, `/admin/answer-flow`, `/admin/observability`, `/admin/experiments`, `/admin/rag-eval`, `/admin/rag-ingestion`) exist solely in `apps/web/` and are not implemented as mobile surfaces. Mobile Admin mode routes to `ClinicalOverviewSurface` with basic telemetry and audit links.
- **Source Anchor**: `docs/ui-modernization/route-capability-matrix.md:87-101`, `apps/mobile/lib/experience/unified/unified_root.dart:220-268`.
- **Impact**: Administrators cannot perform model evaluations, vector index re-indexing, or prompt experiment reviews from mobile devices.
- **Remediation / Workaround**:
  1. Formally document this design boundary: mobile admin presentation is intended for operational status checks and emergency clinician access, while administrative engineering remains desktop-first.

---

### RISK-MOB-06: Strict Offline Mutation Blocking Without Asynchronous Outbox
- **Description**: When offline, `OfflineMutationGuard` intercepts any mutation attempt (saving PHR entries, updating medications, accepting LifeMap tasks) and displays an informative banner while preserving form input in local memory. However, there is no persistent background sync queue/outbox to automatically retry the mutation upon reconnection.
- **Source Anchor**: `apps/mobile/lib/widgets/offline_banner.dart:80-140`.
- **Impact**: Users must manually trigger the action again once the device regains network access. If the user exits the app while offline, uncommitted form inputs stored in ephemeral widget state could be lost.
- **Remediation / Workaround**:
  1. Medical safety invariant: CLARA avoids silent optimistic health writes to prevent conflicting prescription or dosage records.
  2. Keep mutation blocking for safety-critical drug and dosage actions.
  3. In future phases, consider persisting draft notes locally with explicit user-prompted sync upon reconnection.
