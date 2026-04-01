# CLARA Mobile (Flutter Starter)

This folder contains a lightweight Flutter client starter for CLARA mobile integration.

## Included

- Project manifest with core dependencies: `flutter`, `http`
- Linting via `flutter_lints`
- Basic app/screens:
  - `lib/main.dart`
  - `lib/app.dart`
  - `lib/core/api_client.dart`
  - `lib/core/session_store.dart`
  - `lib/screens/login_screen.dart`
  - `lib/screens/dashboard_screen.dart`
  - `lib/screens/research_screen.dart`
  - `lib/screens/careguard_screen.dart`
  - `lib/screens/council_screen.dart`

## API endpoints wired

- Login: `POST /api/v1/auth/login`
- Research Tier 2: `POST /api/v1/research/tier2`
- CareGuard Analyze: `POST /api/v1/careguard/analyze`
- Council Run: `POST /api/v1/council/run`
- System Metrics: `GET /api/v1/system/metrics`

## Setup

1. Install Flutter SDK.
2. From repo root:
   - `cd apps/mobile`
   - `flutter pub get`

Generated platform folders are intentionally excluded from git. To run on a device/emulator, generate platforms locally (do not commit generated folders if not needed):

- `flutter create . --platforms=android,ios,web`

## Run

Use `--dart-define` to configure the backend base URL:

- `flutter run --dart-define=CLARA_API_BASE_URL=http://localhost:8000`

Examples:

- Android emulator: `flutter run -d emulator-5554 --dart-define=CLARA_API_BASE_URL=http://10.0.2.2:8000`
- iOS simulator: `flutter run -d ios --dart-define=CLARA_API_BASE_URL=http://127.0.0.1:8000`

## Notes

- Session storage is in-memory only (resets when app restarts).
- Backend role scaffold behavior:
  - Email ending with `@research.clara` -> `researcher`
  - Email ending with `@doctor.clara` -> `doctor`
