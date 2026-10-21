# Test and Audit Report: Mobile Flutter (PH00_A06)

## 1. Executive Summary & Verification Context

- **Subagent**: `A06`
- **Phase**: `PH00`
- **Role**: `Mobile Flutter`
- **Worktree**: `/dev/shm/clara_worktrees/PH00_A06`
- **Branch**: `phase/ph00-a06`
- **Frozen HEAD SHA**: `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
- **Audit Date**: 2026-10-21
- **Status**: Complete with verified source anchors and identified toolchain constraints.

This report documents the comprehensive static and execution audit of the Flutter mobile application located in `apps/mobile/`, the Android build target, the iOS target status, the Web-to-Mobile route parity inventory, state management architectures, offline caching mechanisms, and real vs. mock API calls.

---

## 2. Test Commands & Non-Destructive Inspection Results

### 2.1 Git Repository Verification
- **Command**: `git rev-parse HEAD && git status`
- **Exit Code**: `0`
- **Output**:
  ```text
  8a48afab1dafa2f8ccb4ac9f320505452d18b30f
  On branch phase/ph00-a06
  nothing to commit, working tree clean
  ```
- **Finding**: Verified working tree is clean and exactly matches frozen HEAD commit `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`.

### 2.2 System Toolchain Detection
- **Command**: `/home/clue/development/flutter/bin/flutter --version`
- **Exit Code**: `0`
- **Output**:
  ```text
  Flutter 3.29.0 • channel [user-branch] • unknown source
  Framework • revision 35c388afb5 (1 year, 8 months ago) • 2025-02-10 12:48:41 -0800
  Engine • revision 010c8a806b
  Tools • Dart 3.7.0 (build 3.7.0-323.0.dev) • DevTools 2.42.0
  ```
- **Finding**: Host system provides Flutter 3.29.0 and Dart 3.7.0 at `/home/clue/development/flutter/bin/flutter`.

### 2.3 Network Reachability Probe
- **Command**: `curl -sI https://pub.dev | head -n 5`
- **Exit Code**: `0`
- **Output**:
  ```text
  HTTP/2 200
  date: Wed, 21 Oct 2026 10:30:13 GMT
  content-type: text/html; charset="utf-8"
  ```
- **Finding**: External network connection to pub package registry is active and functional.

### 2.4 Pub Dependency & SDK Compatibility Check
- **Command**: `/home/clue/development/flutter/bin/flutter pub get --dry-run`
- **Working Directory**: `/dev/shm/clara_worktrees/PH00_A06/apps/mobile`
- **Exit Code**: `1`
- **Stderr/Stdout Output**:
  ```text
  Resolving dependencies...
  The current Dart SDK version is 3.7.0-323.0.dev.

  Because markdown 7.3.1 requires SDK version ^3.9.0 and no versions of markdown match >7.3.1 <8.0.0, markdown ^7.3.1 is forbidden.
  So, because clara_mobile depends on markdown ^7.3.1, version solving failed.

  You can try the following suggestion to make the pubspec resolve:
  * Try using the Flutter SDK version: 3.47.7.
  Failed to update packages.
  ```
- **Finding**: The checked-in `pubspec.lock` contains `markdown: 7.3.1`, which requires Dart SDK `^3.9.0` (corresponding to Flutter 3.47+). The local system installation is Flutter 3.29.0 / Dart 3.7.0. Resolving new dependencies requires upgrading the local Flutter SDK to 3.47.7+ or using a containerized CI environment matching Flutter 3.47+.

### 2.5 Cross-Platform Consumer Terminology Contract Check
- **Command**: `cd apps/web && npm run consumer-terminology:check`
- **Working Directory**: `/dev/shm/clara_worktrees/PH00_A06`
- **Exit Code**: `0`
- **Output**:
  ```text
  v20.20.2

  > clara-web@0.1.0 consumer-terminology:check
  > node scripts/generate-consumer-terminology.mjs --check && node scripts/check-consumer-terminology-contract.mjs

  consumer terminology projection check passed: 19 keys, 2026-07-30.v1.
  consumer terminology contract passed: 19 keys, 2026-07-30.v1.
  ```
- **Finding**: The consumer terminology contract generator is synchronized with both Web (`apps/web/lib/i18n/consumer-terminology.generated.ts`) and Mobile (`apps/mobile/lib/core/consumer_terminology.generated.dart`).

---

## 3. Platform Target Status

### 3.1 Android Target: PRESENT
The Android native wrapper is fully initialized and checked into source control:
- **Root Configuration**: `apps/mobile/android/build.gradle.kts:1-24` defines central build directory routing (`../../build`) and repository configuration (`google()`, `mavenCentral()`).
- **Gradle Settings**: `apps/mobile/android/settings.gradle.kts:20-24` specifies Android Application Plugin `9.0.1`, Kotlin Android Plugin `2.3.20`, and Flutter Gradle plugin loader `1.0.0`.
- **Gradle Wrapper**: `apps/mobile/android/gradle/wrapper/gradle-wrapper.properties:5` points to Gradle `9.1.0-all.zip`.
- **App Module**: `apps/mobile/android/app/build.gradle.kts:7-66` defines:
  - `namespace = "com.theclaracare.app"`
  - `compileOptions` targeting `JavaVersion.VERSION_17`
  - Release signing configuration reading properties `CLARA_RELEASE_STORE_FILE`, `CLARA_RELEASE_STORE_PASSWORD`, `CLARA_RELEASE_KEY_ALIAS`, `CLARA_RELEASE_KEY_PASSWORD` with fallback to `clara-release.jks` or debug keystore.
- **Android Manifest**: `apps/mobile/android/app/src/main/AndroidManifest.xml:1-71` configures:
  - Permission: `android.permission.INTERNET`
  - Single-top activity: `MainActivity`
  - App Links: Intent filters with `android:autoVerify="true"` for `theclaracare.com` and `www.theclaracare.com` under path prefix `/phr/shared/` (`AndroidManifest.xml:30-47`).
  - Rendering backend override: `io.flutter.embedding.android.EnableImpeller = false` (forces Skia engine to allow `adb screencap` captures for automated visual QA).

### 3.2 iOS Target: ABSENT
- **Directory**: `apps/mobile/ios/` does NOT exist on disk.
- **Status Confirmation**: Confirmed via `ls apps/mobile/ios` (error: No such file or directory).
- **Design Intent**: Documented in `apps/mobile/README.md:261-265`, stating that platform folders are generated locally as needed (`flutter create . --platforms=android,ios,web`) and kept out of version control. However, while Android was explicitly scaffolded and committed, iOS remains ungenerated in the repo.

---

## 4. Screen & Route Parity Architecture

### 4.1 Routing Structure
CLARA Mobile utilizes a layered root pattern controlled by compile-time `--dart-define` switches in `apps/mobile/lib/app.dart:95-285`:
1. **Public Share Intake** (`PublicShareLinkController`): Bypasses authentication when an App Link token is supplied, opening `SharedResourceScreen` (`apps/mobile/lib/screens/shared_resource_screen.dart:21`).
2. **Authenticated Root Selection**:
   - `kMobileUnifiedEnabled` (default `true`): Routes to `UnifiedRoot` (`apps/mobile/lib/experience/unified/unified_root.dart:60`).
   - `kMobileRedesignEnabled` (default `false`): Routes to `RedesignRoot` (`apps/mobile/lib/experience/redesign/redesign_root.dart:36`).
   - `kMobileExperienceV2Enabled` (default `false`): Routes to `OnboardingGate` wrapping `AppShell` (`apps/mobile/lib/experience/app_shell.dart:25`).
   - Fallback (legacy): Routes to `DashboardScreen` (`apps/mobile/lib/screens/dashboard_screen.dart:18`).

### 4.2 Presentation Modes (Web/Mobile Parity)
`PresentationModeController` (`apps/mobile/lib/experience/presentation_mode.dart:124`) provides role-governed workspace switching:
- **Personal Mode**: Today (`TodaySurface`), Health Journey (`LifeMapSurface`), Ask CLARA (`ChatSurfaceV3`), Medicines (`MedicinesHub`), Profile (`ProfileHub`).
- **Clinical Mode**: Clinician Command Center (`ClinicalOverviewSurface`), AI Council (`CouncilSurfaceV3`), Medical Scribe (`ScribeSurfaceV3`), More Menu (`MoreScreenV3`).
- **Research Mode**: Living Evidence (`LivingEvidenceSurface`), Source Hub (`ResearchScreen`), More Menu (`MoreScreenV3`).
- **Administration Mode**: Overview with System Metrics (`ClinicalOverviewSurface`, `getSystemMetrics`), More Menu.

### 4.3 Web-to-Mobile Parity Findings
- **High Parity**: All consumer-facing workflows (Today, LifeMap, Medication Cabinet, CareGuard DDI checks, Scribe recording & SOAP notes, AI Council deliberation, Family Sharing, PDPD Consent, and DSAR requests) have full parity with the Web application.
- **Public Capabilities**: Sharing via `/phr/shared/[token]` is supported natively on Android through verified App Links.
- **Admin Gap**: Backoffice configuration portals (`/admin/knowledge-sources`, `/admin/answer-flow`, `/admin/observability`, `/admin/experiments`, `/admin/rag-eval`) are desktop Web-exclusive; mobile exposes only system metrics and audit compliance links.

---

## 5. State Management & Offline Caching Audit

### 5.1 State Management Architecture
- **Session & Auth State**: Managed by `SessionStore` (`apps/mobile/lib/core/session_store.dart:98`), a `ChangeNotifier` backed by `flutter_secure_storage`. Restores session upon app launch via `hydrate()`, handles JWT decoding, and synchronizes access and refresh tokens.
- **Appearance & Locale**: `ThemeController` and `LanguageController` extend `ChangeNotifier`, persisting to `ThemePreferenceStore` (default light mode) and `LanguageStore` (default Vietnamese `vi`).
- **Workspace Navigation**: `PresentationModeController` dynamically switches destinations without bypassing backend RBAC rules.
- **Surface Scoping**: Translucent glass styling is managed via `GlassScopeProvider` (`apps/mobile/lib/theme/glass/glass_scope.dart:36`), which degrades glass effects to solid colors on resource-constrained devices.

### 5.2 Offline Caching & Resilience
1. **CareGuard DDI Offline Fallback**:
   - Class: `CareguardOfflineCache` (`apps/mobile/lib/core/careguard_offline_cache.dart:71`).
   - Storage: Encrypted in platform secure storage, scoped to user ID.
   - Guardrails: Caches strictly the 4 End_User fields; strips internal metadata; labels results as `offline / không phải thời gian thực`; misses return `null` rather than fabricating an all-clear.
2. **LifeMap Today Read Cache**:
   - Class: `LifeMapReadCache` (`apps/mobile/lib/core/lifemap_read_cache.dart:31`).
   - Storage: Encrypted 15-minute projection of tasks and episodes; all mutations remain disabled while reading from cache.
3. **Session Store Cache Purge**:
   - Method: `SessionStore._purgeOfflineCaches` (`apps/mobile/lib/core/session_store.dart:178`).
   - Cleans all cached DDI projections, LifeMap tasks, and capture sessions when the user logs out or switches accounts.
4. **Network Detection & Mutation Guards**:
   - `ConnectivityService` (`apps/mobile/lib/core/connectivity_service.dart:16`): Broadcast stream for real-time reachability changes.
   - `OfflineBanner` & `OfflineMutationGuard` (`apps/mobile/lib/widgets/offline_banner.dart:48`): Blocks state-mutating API calls while offline and retains user inputs to prevent data loss.

---

## 6. Mock vs. Real API Audit

- **Production Code (`apps/mobile/lib/`)**:
  - `ApiClient` (`apps/mobile/lib/core/api_client.dart:14-1380`) performs 100% real HTTP calls using `package:http/http.dart`.
  - Configured with `_defaultApiBaseUrl` defaulting to `https://theclaracare.com` in release builds and `http://localhost:8100` in debug builds.
  - Features real SSE streaming (`_streamSse`) for AI Chat and Research jobs.
  - Implements automatic pre-flight token expiry check and single 401 refresh retry with request deduplication (`_refreshInFlight`).
  - No synthetic mocks or hardcoded data fallbacks exist in production code paths.
- **Test Code (`apps/mobile/test/`)**:
  - All mocking is quarantined in `apps/mobile/test/fakes/fake_api_client.dart` via `FakeApiClient`.
  - `FakeApiClient` extends `ApiClient` with `_UnusableHttpClient`, which throws a `StateError` if any un-stubbed request attempts network I/O, ensuring deterministic and safe offline test execution.

---

## 7. Deliverable Verification Checklist

- [x] Verified frozen HEAD SHA `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
- [x] Inspected `apps/mobile/lib/`, `pubspec.yaml`, `android/`, confirmed iOS status (ABSENT)
- [x] Recorded exact `path:line` anchors for all inspected files
- [x] Wrote `change_manifest.json`, `test_report.md`, and `risk_register.md` in lane `artifacts/PH00/A06/`
- [x] Performed non-destructive toolchain inspections and contract checks
