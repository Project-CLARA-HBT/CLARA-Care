#!/usr/bin/env bash
# Build the CLARA mobile release APK (Experience_V3 redesign) with the
# production API base URL. Reuses the locally-provisioned JDK17 + Android SDK.
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MOBILE="$ROOT/apps/mobile"

export JAVA_HOME="$HOME/clara-toolchain/jdk17/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_SDK_ROOT="$HOME/Library/Android/sdk"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"

FLUTTER=/usr/local/bin/flutter
API_BASE="${CLARA_API_BASE_URL:-https://theclaracare.com}"

cd "$MOBILE" || { echo "no mobile dir"; exit 1; }

echo "== ensure android project =="
[ -d android ] || "$FLUTTER" create --platforms=android --project-name clara_mobile . 2>&1 | tail -8

echo "== pub get =="
for a in 1 2 3; do "$FLUTTER" pub get 2>&1 | tail -6 && break; sleep 5; done

echo "== build apk (redesign, base=$API_BASE) =="
"$FLUTTER" build apk --release \
  --dart-define=MOBILE_REDESIGN_ENABLED=true \
  --dart-define=MOBILE_LIQUID_GLASS_ENABLED=true \
  --dart-define=MOBILE_UX_POLISH_ENABLED=true \
  --dart-define=CHAT_MOBILE_ENABLED=true \
  --dart-define=COUNCIL_MOBILE_PARITY_ENABLED=true \
  --dart-define=CAREGUARD_MOBILE_CABINET_ENABLED=true \
  --dart-define=CLARA_API_BASE_URL="$API_BASE" 2>&1 | tail -40

APK=build/app/outputs/flutter-apk/app-release.apk
if [ -f "$APK" ]; then
  mkdir -p "$ROOT/dist"
  OUT="$ROOT/clara-mobile-release.apk"
  cp "$APK" "$OUT"
  cp "$APK" "$ROOT/dist/clara-mobile-release.apk"
  echo "APK_OK: $OUT ($(ls -lh "$APK" | awk '{print $5}'))"
else
  echo "APK_MISSING"
  exit 1
fi
