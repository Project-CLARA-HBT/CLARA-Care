# CLARA Mobile (Flutter Starter)

This folder contains the Flutter client for CLARA mobile integration. New
End_User-facing surfaces ship behind feature flags that default to OFF, so a
plain build behaves exactly like the original six-screen app (login, research,
CareGuard, council, dashboard, PHR) until a flag is explicitly enabled.

## Included

- Project manifest with core dependencies: `flutter`, `http`,
  `flutter_secure_storage`
- Linting via `flutter_lints`
- Basic app/screens:
  - `lib/main.dart`
  - `lib/app.dart`
  - `lib/core/api_client.dart`
  - `lib/core/session_store.dart`
  - `lib/core/feature_flags.dart`
  - `lib/screens/login_screen.dart`
  - `lib/screens/dashboard_screen.dart`
  - `lib/screens/research_screen.dart`
  - `lib/screens/careguard_screen.dart`
  - `lib/screens/council_screen.dart`
  - `lib/screens/phr_screen.dart`

## API endpoints wired

- Login: `POST /api/v1/auth/login`
- Token refresh: `POST /api/v1/auth/refresh`
- Mobile summary: `GET /api/v1/mobile/summary`
- Research Tier 2: `POST /api/v1/research/tier2`
- CareGuard Analyze: `POST /api/v1/careguard/analyze`
- Council Run: `POST /api/v1/council/run`
- System Metrics: `GET /api/v1/system/metrics`

## Session handling

Credentials are persisted in **platform secure storage** (Keychain on iOS,
Keystore-backed `EncryptedSharedPreferences` on Android) via
`flutter_secure_storage`. The session survives app restarts:

- On launch the app hydrates the stored session. A valid (unexpired) token
  restores the authenticated session; an expired or unparseable token clears
  the store and routes back to the login screen.
- The API client refreshes an about-to-expire access token before a request
  and retries once against `/auth/refresh` on a `401`, persisting the new
  credentials or clearing the session on failure.
- Logout (`clear`) removes all credentials from memory and secure storage.

No PII is written to client logs or analytics surfaces.

## Configuration

### API base URL

The default API base URL is `http://localhost:8100`, aligned with the
documented local gateway port (`8100`). Override it at build/run time:

```
--dart-define=CLARA_API_BASE_URL=http://localhost:8100
```

Common overrides for device/emulator networking:

- Android emulator: `--dart-define=CLARA_API_BASE_URL=http://10.0.2.2:8100`
- iOS simulator: `--dart-define=CLARA_API_BASE_URL=http://127.0.0.1:8100`

### Feature flags

Each new surface is gated by a `--dart-define` flag that defaults to `false`.
A gate also opens when the server grants the matching `feature_flags` key for
the authenticated role in `GET /api/v1/mobile/summary`; the compile-time
defines exist for staged enablement and QA/dev builds. Enable a flag with
`--dart-define=<FLAG>=true`.

New mobile feature flags (define name → server `feature_flags` key → surface):

| `--dart-define` flag                  | Server flag key                    | Surface |
| ------------------------------------- | ---------------------------------- | ------- |
| `CHAT_MOBILE_ENABLED`                 | `chat_mobile_enabled`              | Conversational chat |
| `SELFMED_CABINET_MOBILE_ENABLED`      | `selfmed_cabinet_mobile_enabled`   | Self-med medicine-cabinet CRUD feeding the DDI check |
| `SCRIBE_MOBILE_ENABLED`               | `scribe_mobile_enabled`            | Ambient scribe |
| `PHR_ENHANCED_MOBILE_ENABLED`         | `phr_enhanced_mobile_enabled`      | Enhanced PHR reads (export + emergency card) |
| `MODEL_DISCLOSURE_MOBILE_ENABLED`     | `model_disclosure_mobile_enabled`  | Model family/version disclosure chips |
| `TRANSPARENCY_NOTICE_MOBILE_ENABLED`  | `transparency_notice_mobile_enabled` | Versioned AI transparency notice |
| `CONSENT_CENTER_MOBILE_ENABLED`       | `consent_center_mobile_enabled`    | Granular consent center + DSAR self-service |
| `SHARING_MOBILE_ENABLED`              | `sharing_mobile_enabled`           | Read-only shared-resource / deep-link surface |

Existing build-time flags (also default OFF):

| `--dart-define` flag                  | Surface |
| ------------------------------------- | ------- |
| `COUNCIL_MOBILE_PARITY_ENABLED`       | Council case-based parity flow (otherwise the legacy `CouncilScreen`) |
| `CAREGUARD_MOBILE_CABINET_ENABLED`    | CareGuard cabinet CRUD parity screen |

Multiple flags can be combined on a single command, e.g.:

```
flutter run \
  --dart-define=CLARA_API_BASE_URL=http://localhost:8100 \
  --dart-define=CHAT_MOBILE_ENABLED=true \
  --dart-define=PHR_ENHANCED_MOBILE_ENABLED=true
```

## Setup

1. Install Flutter SDK.
2. From repo root:
   - `cd apps/mobile`
   - `flutter pub get`

Generated platform folders are intentionally excluded from git. To run on a
device/emulator, generate platforms locally (do not commit generated folders
if not needed):

- `flutter create . --platforms=android,ios,web`

## Run

```
flutter run --dart-define=CLARA_API_BASE_URL=http://localhost:8100
```

Append any feature flags as additional `--dart-define` arguments (see above).

## Test

Run the widget and unit/property test suite:

```
flutter test
```

## Build

Build a release Android APK:

```
flutter build apk --dart-define=CLARA_API_BASE_URL=https://<your-gateway-host>
```

Production builds ship with all feature-flag defines OFF; the server's
role-scoped `feature_flags` are authoritative there.

## Branding (Experience_V2)

CLARA branding — display name, adaptive launcher icon, and themed splash — is
applied per platform by an operator. The steps (manifest/plist keys, asset
sizes, and the optional `flutter_launcher_icons` / `flutter_native_splash`
generators) are documented in **[docs/branding.md](docs/branding.md)**.

- App display name: **CLARA** (Android `android:label`, iOS
  `CFBundleDisplayName` / `CFBundleName`).
- Splash + adaptive-icon background use the brand seed
  `ClaraTokens.brandSeed` (`0xFF0F766E`), matching the Material 3 theme.
- **No binaries are committed.** Assets and platform folders are generated
  **locally** and kept out of git; the generator packages are optional/manual
  (no forced `pubspec.yaml` dependency).
- The themed splash adds **no artificial delay** — the existing `_LaunchSplash`
  shows only while `SessionStore.hydrate()` runs (launch stays hydration-driven).

## Notes

- Backend role scaffold behavior:
  - Email ending with `@research.clara` -> `researcher`
  - Email ending with `@doctor.clara` -> `doctor`
