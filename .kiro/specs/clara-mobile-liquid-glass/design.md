# Design Document

Clara Mobile — Liquid Glass modernization (Experience_V3.1).

## Overview

This design layers an iOS-26 "Liquid Glass" material system onto the existing
Experience_V3 redesign, deepens the Home and Cabinet surfaces (including
camera/photo OCR medication capture), and enables the full admin feature set on
mobile. Everything is additive and gated; the safety-first invariants
(glass = chrome only, clinical content = opaque AA surfaces) are hard
constraints.

### Design principles (from research)

- **Glass is the navigation/control layer, never the content layer.** Blur +
  translucency + specular edge + soft shadow via built-in `BackdropFilter`
  gives ~80% of the look with zero risky dependencies. True refraction shaders
  are explicitly out of scope.
- **Fail-closed everywhere.** New gate `MOBILE_LIQUID_GLASS_ENABLED` defaults
  OFF; when off the app is byte-for-byte Experience_V3. Reduced-transparency /
  low-end devices get an opaque fallback automatically.
- **Reuse over rebuild.** Restyle existing V3 surfaces and reuse their data
  contracts, gating, and safety projections; do not re-implement flows.

## Architecture

### Gate hierarchy (build-time)

```
MOBILE_REDESIGN_ENABLED (existing, chooses Experience_V3 root)
  └─ MOBILE_LIQUID_GLASS_ENABLED (new, default false)
        controls: glass chrome material on/off across V3 surfaces
```

`kMobileLiquidGlassEnabled` is read in exactly one place per surface (via a
small `GlassScope` inherited widget seeded at the redesign root) so surfaces ask
"is glass on?" rather than re-reading the define. When off, `GlassSurface`
degrades to a plain opaque container = current V3 look.

### New/changed modules (mobile)

```
lib/theme/glass/
  glass_tokens.dart        # blur sigma, fill opacities, borders, sheen, shadows, radii
  glass_surface.dart       # GlassSurface widget + reduced-transparency/low-end fallback
  glass_scope.dart         # InheritedWidget: glassEnabled resolved once (define + a11y + device tier)
lib/core/
  device_capability.dart   # low-end/battery-saver + reduce-transparency probe (platform channel + heuristics)
  api_client.dart          # + scanCareguardCabinetFile(...) and importCareguardDetections(...)
lib/experience/redesign/
  home_screen_v3.dart      # richer sectioned Home with glass hero
  cabinet_screen_v3.dart   # OCR capture flow + modern item cards
  cabinet_ocr_sheet.dart   # (new) capture → review/confirm → import bottom sheet
  redesign_shell.dart      # glass bottom bar + glass FAB
  redesign_root.dart       # wrap in GlassScope
```

New pub dependencies (pinned): `image_picker` (camera + gallery). No shader
packages. `ContinuousRectangleBorder` (built-in) is used for squircles; a
squircle helper is added to `GlassTokens` (×1.7 radius rule) to avoid a new dep
unless designers require `figma_squircle` later.

### Reduced-transparency / device-tier resolution

`GlassScope.glassEnabled = kMobileLiquidGlassEnabled && !reduceTransparency &&
!lowEndDevice`. Signals:

- Reduce Transparency / high contrast: `MediaQuery.highContrast`, `boldText`,
  `disableAnimations`, plus (iOS) a platform-channel read of
  `UIAccessibility.isReduceTransparencyEnabled`; Android treats
  battery-saver / "remove animations" as the degrade signal.
- Low-end: heuristic from Android SDK/RAM tier (cached once at startup). A
  conservative default (glass ON) applies when the probe is unavailable, since
  the fallback is only a visual downgrade.

Even when `glassEnabled` is true globally, `GlassSurface` still renders opaque
for any instance flagged `clinical: true` — a belt-and-suspenders guard so a
misuse can't put blur behind medical text.

## Components and Interfaces

### GlassTokens (light-first)

| Role | Blur σ | Fill (white α) |
|---|---|---|
| Bottom nav / tab bar | 24 | 0.45 (thin) |
| Top bar / app bar | 20 | 0.45 |
| Floating card / chip | 12 | 0.60 (regular) |
| Sheet header | 30 | 0.75 (thick) |

Borders: hairline white α0.70, width 1. Sheen: topLeft→bottomRight linear
α0.22→0→0.08. Shadows: ambient (black α0.06, blur 24, y+8) + contact (black
α0.04, blur 6, y+2). Radii (outer): chip 12, control 16, card 24, sheet 32;
squircle via `ContinuousRectangleBorder(borderRadius × 1.7)`. Dark-mode fills
use a dark tint (α on near-surface) computed from `WebPalette.dark*`.

### GlassSurface

```dart
GlassSurface({
  required Widget child,
  double blurSigma = GlassTokens.blurCard,
  double radius = GlassTokens.rCard,
  Color? fill,
  EdgeInsets padding,
  bool clinical = false,   // force-opaque regardless of glassEnabled
})
```

Composition: `RepaintBoundary` → `DecoratedBox(shadows)` → `ClipPath(squircle)`
→ (`BackdropFilter(blur, TileMode.mirror)` when glass on) → `Container(fill +
foreground sheen/border)` → child. When glass off/clinical/fallback: skip the
`BackdropFilter`, use `fillOpaque` (α0.92) or a fully opaque scheme surface.

### API client additions

```dart
// POST /api/v1/careguard/cabinet/scan-file  (multipart, field "file")
Future<Map<String,dynamic>> scanCareguardCabinetFile({
  required String accessToken,
  required List<int> fileBytes,
  required String filename,
});

// POST /api/v1/careguard/cabinet/import-detections  (JSON {detections:[...]})
Future<Map<String,dynamic>> importCareguardDetections({
  required String accessToken,
  required List<Map<String,dynamic>> detections,
});
```

Both reuse the existing `_postMultipart` / `_post` helpers. Response parsing
mirrors the server schema: `detections[]` (drug_name, normalized_name, dosage,
brand_name, manufacturer, confidence, requires_manual_confirm), `confirm_gate`
(threshold, requires_confirmation), `prioritized_fields`.

### Cabinet OCR sheet (new)

A `GlassSurface`-headed bottom sheet: **Capture** (camera/gallery via
`image_picker`) → **Review** (each detection as an opaque card with a confirm
checkbox; low-confidence pre-unchecked and labeled "cần xác nhận") → **Import**
(enabled only when the confirm-gate is satisfied). No detection is imported
unless its card is confirmed. Offline blocks capture/import with the standard
message. Analytics: coarse counts only (`detection_count`, `imported_count`) —
never drug names.

### Server flag change

`services/api/.../endpoints/mobile.py` `_FEATURE_FLAGS_BY_ROLE['admin']` is
expanded to include every client-consumed key = `true`. Other roles unchanged.
The response schema (`MobileSummaryResponse.feature_flags: dict[str,bool]`)
already permits arbitrary keys, so no schema change is needed. A test asserts
admin emits the full set and non-admin roles are untouched.

## Data Models

No new persistent models. OCR detections are transient (server-owned). Home
"stat cards" read only already-loaded data (cabinet count via existing cabinet
GET, PHR presence via existing PHR GET) — no new endpoints; if a datum requires
a call the surface already makes, it is reused, otherwise omitted.

## Error Handling

- OCR: camera/permission denied → fall back to manual add with a non-blocking
  banner; scan 4xx/5xx → inline error + retry, cabinet unchanged; empty
  detections → "không nhận diện được thuốc, thử lại hoặc nhập tay".
- Glass: probe failure → default glass ON (visual-only risk); any render
  exception in `GlassSurface` cannot affect content because content is a child
  rendered independently of the backdrop layer.
- Model swap: if health checks fail after restart, roll back the `.env` model
  keys and restart (documented in tasks).

## Testing Strategy

- Unit/property: `GlassScope.glassEnabled` truth table (define × reduce-transp ×
  low-end); `GlassSurface` renders no `BackdropFilter` when off/clinical/fallback.
- Widget: Home fail-closed tool derivation + sectioned layout; Cabinet OCR
  confirm-gate (unconfirmed ⇒ import disabled ⇒ no `importCareguardDetections`
  call), offline block, DDI two-medicine guard intact; clinical surfaces have no
  ancestor `BackdropFilter`.
- Server: pytest asserting `mobile/summary` admin flag set is complete and
  non-admin roles unchanged; RBAC 403 preserved.
- A11y: ≥48dp targets, text scaler 1.6×, reduced-motion collapses glass motion.
- Build/deploy: Android release with `MOBILE_REDESIGN_ENABLED=true
  MOBILE_LIQUID_GLASS_ENABLED=true` pointing at `clara.thiennn.icu`, installed on
  device.

## Non-Goals

- Fragment-shader refraction / the `liquid_glass_renderer` package.
- Any change to the ML pipeline beyond the `.env` model swap.
- New server persistence or endpoints for Home stats or OCR (reuse existing).
