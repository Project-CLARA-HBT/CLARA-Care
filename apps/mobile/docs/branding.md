# CLARA Mobile Branding (Experience_V2)

This document describes how an operator applies CLARA branding — **display
name**, **adaptive launcher icon**, and **themed splash** — to the Flutter
client. It is **documentation only**: it lists the manifest/plist keys, the
asset sizes, and the optional generator packages an operator runs locally.

> **No binaries policy.** This repository intentionally commits **no large
> binary image assets** (launcher icons, splash images) and **no generated
> platform folders** (`android/`, `ios/`). Generate platforms and brand assets
> **locally** (`flutter create .`) and keep them out of git, mirroring the
> repo's existing no-binary policy. The snippets below show what the generated
> files should contain so the result is reproducible without committing PNGs.

## Brand reference

| Token | Value | Use |
| ----- | ----- | --- |
| App brand (product name) | **CLARA** | Display name on both platforms |
| Brand seed color (`ClaraTokens.brandSeed`) | `0xFF0F766E` (teal, `#0F766E`) | M3 `ColorScheme.fromSeed` seed **and** the themed splash background |

The splash background color **must** match `ClaraTokens.brandSeed`
(`lib/theme/tokens.dart`) so the launch surface, the M3 theme, and the launcher
icon background read as one coherent brand. Provide a light and a dark splash
variant that follow OS brightness, consistent with the light/dark M3 themes.

---

## 1. Display name (Req 8.1)

Set a human-readable display name of **CLARA** on both platforms.

### Android — `android/app/src/main/AndroidManifest.xml`

Set `android:label` on the `<application>` element. If any `<activity>` carries
its own `android:label`, set it to the same value (or remove it so it inherits
from the application).

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:label="CLARA"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round">
        <activity
            android:name=".MainActivity"
            android:label="CLARA"
            android:exported="true">
            <!-- launcher intent-filter ... -->
        </activity>
    </application>
</manifest>
```

> Prefer a string resource (`android:label="@string/app_name"` with
> `app_name=CLARA` in `android/app/src/main/res/values/strings.xml`) if you
> need localized names; a literal `"CLARA"` is fine for a single brand name.

### iOS — `ios/Runner/Info.plist`

`CFBundleDisplayName` is the name shown under the icon on the home screen;
`CFBundleName` is the shorter internal product name.

```xml
<key>CFBundleDisplayName</key>
<string>CLARA</string>
<key>CFBundleName</key>
<string>CLARA</string>
```

---

## 2. Adaptive launcher icon (Req 8.2)

### Android adaptive icon

Android 8.0+ (API 26) uses **adaptive icons** composed of a **foreground** and
a **background** layer drawn on a **108×108 dp** canvas, of which only the
central **72×72 dp** is the guaranteed **safe zone** (the launcher masks/animates
the outer ~18 dp on each side). Keep the CLARA glyph inside the 72 dp safe zone.

`android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
    <!-- Optional API 33+ themed/monochrome layer -->
    <monochrome android:drawable="@mipmap/ic_launcher_foreground" />
</adaptive-icon>
```

Define the background as the brand seed in
`android/app/src/main/res/values/colors.xml`:

```xml
<resources>
    <color name="ic_launcher_background">#0F766E</color>
</resources>
```

Reference both `android:icon="@mipmap/ic_launcher"` and
`android:roundIcon="@mipmap/ic_launcher_round"` from the manifest (see §1).

**Required legacy mipmap densities** (square `ic_launcher.png`, used by
pre-API-26 launchers and as the `roundIcon` fallback):

| Density bucket | Folder | Size (px) |
| -------------- | ------ | --------- |
| mdpi   | `mipmap-mdpi`    | 48 × 48 |
| hdpi   | `mipmap-hdpi`    | 72 × 72 |
| xhdpi  | `mipmap-xhdpi`   | 96 × 96 |
| xxhdpi | `mipmap-xxhdpi`  | 144 × 144 |
| xxxhdpi| `mipmap-xxxhdpi` | 192 × 192 |

The adaptive **foreground** PNGs (`ic_launcher_foreground.png`) live in the
same density buckets sized to the **108 dp** canvas (e.g. 432 × 432 px at
xxxhdpi), with the artwork inside the 72 dp safe zone.

### iOS app icon

Provide the icon set in
`ios/Runner/Assets.xcassets/AppIcon.appiconset/` with a `Contents.json`
mapping each size. Modern Xcode accepts a **single 1024 × 1024** image (no alpha)
and downsizes, but the classic complete set is:

| Purpose | Size (px) |
| ------- | --------- |
| App Store marketing | 1024 × 1024 |
| iPhone app (@3x / @2x) | 180 × 180 / 120 × 120 |
| iPhone spotlight (@3x / @2x) | 120 × 120 / 80 × 80 |
| iPhone settings (@3x / @2x) | 87 × 87 / 58 × 58 |
| iPhone notification (@3x / @2x) | 60 × 60 / 40 × 40 |
| iPad app (@2x / @1x) | 152 × 152 / 76 × 76 |
| iPad Pro app (@2x) | 167 × 167 |

> iOS icons must be **opaque** (no transparency) and have **no** rounded
> corners — the system applies the mask.

---

## 3. Themed splash (Req 8.2, 8.5)

The splash background is the brand seed `#0F766E` (`ClaraTokens.brandSeed`),
matching the M3 theme, with a centered CLARA logo.

### Android 12+ (API 31+) — splash screen theme

Android 12 introduced the system splash screen API. Define a `splashScreenTheme`
and reference it from the launcher activity.

`android/app/src/main/res/values-v31/styles.xml`:

```xml
<resources>
    <style name="LaunchTheme" parent="@style/Theme.SplashScreen">
        <item name="android:windowSplashScreenBackground">#0F766E</item>
        <item name="android:windowSplashScreenAnimatedIcon">@drawable/ic_splash_logo</item>
        <!-- Hands off to the normal theme once Flutter is ready -->
        <item name="postSplashScreenTheme">@style/NormalTheme</item>
    </style>
</resources>
```

Provide a `values-night-v31/styles.xml` with the dark variant if the dark
splash differs.

### Legacy launch background (pre-API 31 / iOS parity drawable)

`android/app/src/main/res/drawable/launch_background.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:drawable="@color/ic_launcher_background" />
    <item android:gravity="center">
        <bitmap android:src="@mipmap/ic_splash_logo" />
    </item>
</layer-list>
```

### iOS — `ios/Runner/Base.lproj/LaunchScreen.storyboard`

Set the storyboard root view background to the brand seed and center the CLARA
logo image (added to `Assets.xcassets` as `LaunchImage`). Use a solid
`#0F766E` background view with a centered `UIImageView`. A `LaunchBackground`
color set in the asset catalog can carry separate light/dark values.

---

## 4. Optional / manual generator packages (Req 8.4)

The launcher icon and splash assets above are normally produced by generator
packages. **They are optional dev-time tools**: an operator runs them **locally**
to emit the PNGs/XML, which are then **not committed** (license + binary size).
Do **not** add them as forced runtime dependencies in `pubspec.yaml`.

If you choose to use them, add them under `dev_dependencies` locally and run
them once, then discard or `.gitignore` the generated binaries:

```yaml
# pubspec.yaml — OPTIONAL, dev-time only; do not commit generated assets
dev_dependencies:
  flutter_launcher_icons: ^0.13.1
  flutter_native_splash: ^2.4.0

flutter_launcher_icons:
  android: true
  ios: true
  image_path: "branding/clara_icon_1024.png"          # local, not committed
  adaptive_icon_background: "#0F766E"                   # ClaraTokens.brandSeed
  adaptive_icon_foreground: "branding/clara_fg.png"     # local, not committed

flutter_native_splash:
  color: "#0F766E"                # ClaraTokens.brandSeed (light)
  color_dark: "#0F766E"           # dark variant (adjust if needed)
  image: "branding/clara_splash.png"        # local, not committed
  android_12:
    color: "#0F766E"
    image: "branding/clara_splash.png"
```

Run locally:

```
flutter pub run flutter_launcher_icons
dart run flutter_native_splash:create
```

Then verify the generated `mipmap-*`, `Assets.xcassets`, and splash
styles/storyboard per platform, and ensure the binaries stay **out of git**
(they belong in a local `branding/` working directory or your asset pipeline,
not the repo).

---

## 5. Launch hydration must not be delayed (Req 8.5)

Branding is **visual only**. The themed splash **must not** introduce a fixed
artificial delay or block launch.

The app already shows a hydration-gated launch surface (`_LaunchSplash` in
`lib/app.dart`) that is visible **only while `SessionStore.hydrate()` runs** —
it disappears as soon as hydration completes (`ConnectionState.done`). The
system/native splash (Android 12 splash screen, iOS `LaunchScreen.storyboard`)
covers the brief window before the first Flutter frame and then hands off to
this hydration gate.

Do **not**:

- add a timer / `Future.delayed` to keep the splash on screen,
- gate routing on anything other than session hydration,
- block the first frame waiting on branding assets.

The launch sequence remains driven by session hydration; branding only changes
how that window **looks**, never how long it lasts.

---

## References

- Brand seed: `apps/mobile/lib/theme/tokens.dart` → `ClaraTokens.brandSeed` (`0xFF0F766E`)
- Hydration-gated launch: `apps/mobile/lib/app.dart` → `_LaunchSplash` / `_buildHome`
- M3 theme: `apps/mobile/lib/theme/clara_theme.dart` → `ClaraTheme.light()/dark()`
