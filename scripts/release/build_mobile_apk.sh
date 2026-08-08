#!/usr/bin/env bash
# Build the CLARA mobile release APK (Unified experience) with the production
# API base URL. Toolchain locations come from PATH/JAVA_HOME/ANDROID_HOME so
# the same script works on developer machines and release runners.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MOBILE="$ROOT/apps/mobile"

FLUTTER="${FLUTTER_BIN:-$(command -v flutter || true)}"
API_BASE="${CLARA_API_BASE_URL:-https://theclaracare.com}"

if [ -z "$FLUTTER" ] || [ ! -x "$FLUTTER" ]; then
  echo "Flutter executable not found; set FLUTTER_BIN or add flutter to PATH." >&2
  exit 1
fi

for required in \
  ORG_GRADLE_PROJECT_CLARA_RELEASE_STORE_FILE \
  ORG_GRADLE_PROJECT_CLARA_RELEASE_STORE_PASSWORD \
  ORG_GRADLE_PROJECT_CLARA_RELEASE_KEY_ALIAS \
  ORG_GRADLE_PROJECT_CLARA_RELEASE_KEY_PASSWORD; do
  if [ -z "${!required:-}" ]; then
    echo "Missing required signed-release input: $required" >&2
    exit 1
  fi
done

if [ ! -s "$ORG_GRADLE_PROJECT_CLARA_RELEASE_STORE_FILE" ]; then
  echo "Release keystore is missing or empty." >&2
  exit 1
fi

cd "$MOBILE"

echo "== ensure android project =="
[ -d android ] || { echo "Committed Android project is missing." >&2; exit 1; }

echo "== pub get =="
"$FLUTTER" pub get

echo "== build apk (unified, base=$API_BASE) =="
# The unified root is the only client-side default we force here. Additive
# medical/clinical surfaces stay server-role-gated in production; do not turn
# their rollout flags into permanent build defaults in a release artifact.
"$FLUTTER" build apk --release \
  --dart-define=MOBILE_UNIFIED_ENABLED=true \
  --dart-define=CLARA_API_BASE_URL="$API_BASE"

APK=build/app/outputs/flutter-apk/app-release.apk
if [ -f "$APK" ]; then
  APKSIGNER="${APKSIGNER_BIN:-}"
  if [ -z "$APKSIGNER" ] && [ -n "${ANDROID_HOME:-}" ]; then
    APKSIGNER="$(find "$ANDROID_HOME/build-tools" -path '*/apksigner' -type f 2>/dev/null | sort -V | tail -1)"
  fi
  if [ -z "$APKSIGNER" ] || [ ! -x "$APKSIGNER" ]; then
    echo "apksigner not found; set APKSIGNER_BIN or ANDROID_HOME." >&2
    exit 1
  fi
  "$APKSIGNER" verify --verbose "$APK"
  mkdir -p "$ROOT/dist"
  OUT="$ROOT/clara-mobile-release.apk"
  cp "$APK" "$OUT"
  cp "$APK" "$ROOT/dist/clara-mobile-release.apk"
  echo "APK_OK: $OUT ($(ls -lh "$APK" | awk '{print $5}'))"
else
  echo "APK_MISSING"
  exit 1
fi
