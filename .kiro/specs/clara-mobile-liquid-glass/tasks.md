# Implementation Plan: Clara Mobile Liquid Glass (Experience_V3.1)

Feature dir: `apps/mobile`. All work is additive behind
`MOBILE_LIQUID_GLASS_ENABLED` (default OFF). Reuse the Experience_V3 surfaces,
data contracts, gating, and safety projections. `flutter analyze` must stay
clean and `flutter test` green for redesign + new files.

## Tasks

- [x] 1. Glass design system foundation
  - [x] 1.1 Add `lib/theme/glass/glass_tokens.dart`: blur sigma, fill opacities
    (thin/regular/thick/opaque), hairline border, sheen gradient, layered
    shadows, radii, and a squircle `ShapeBorder` helper (`ContinuousRectangleBorder`
    ×1.7). Light + dark values from `WebPalette`. Requirement 1.
  - [ ] 1.2 Add `lib/core/device_capability.dart`: reduce-transparency + low-end/
    battery-saver probe (platform-channel best-effort + heuristics, cached once).
    Requirement 1.5, 6.
  - [ ] 1.3 Add `lib/theme/glass/glass_scope.dart` (`InheritedWidget`) resolving
    `glassEnabled = define && !reduceTransparency && !lowEnd`; and
    `glass_surface.dart` (`GlassSurface` with `clinical` force-opaque + fallback).
    Requirement 1, 6.
  - [ ] 1.4 Add build gate `kMobileLiquidGlassEnabled` to `feature_flags.dart`;
    seed `GlassScope` at `redesign_root.dart`. Requirement 1.1.
  - [ ] 1.5 Tests: `glassEnabled` truth table; `GlassSurface` emits no
    `BackdropFilter` when off/clinical/fallback. Requirement 1, 6, 7.

- [ ] 2. Glass chrome across the shell
  - [ ] 2.1 Restyle `redesign_shell.dart`: glass bottom bar + glass circular Chat
    FAB (thin fill, blur, specular edge, soft shadow), squircle corners; selection
    and centered-Chat behavior unchanged. Requirement 2.
  - [ ] 2.2 Apply glass app bars / sheet headers on V3 surfaces via `GlassSurface`;
    keep clinical bodies opaque. Requirement 2, 7.
  - [ ] 2.3 Shell tests: glass on ⇒ chrome uses `GlassSurface`; glass off ⇒ opaque,
    layout identical; center Chat still opens Chat. Requirement 2.

- [ ] 3. Richer, modern Home
  - [ ] 3.1 Rebuild `home_screen_v3.dart`: glass hero greeting card, at-a-glance
    stat row (reusing already-loaded data only), role-aware quick-action grid on
    glass cards, recent-activity section, pull-to-refresh, skeleton/empty/error.
    Fail-closed tool derivation preserved. Requirement 3.
  - [ ] 3.2 Home tests: null summary ⇒ no privileged cards; sections render;
    stat row uses no fabricated data. Requirement 3.5, 3.6.

- [ ] 4. CareGuard cabinet OCR capture + modern cards
  - [ ] 4.1 Add `image_picker` dep (pinned); add `scanCareguardCabinetFile` +
    `importCareguardDetections` to `api_client.dart` (multipart + JSON, reusing
    existing helpers). Requirement 4.
  - [ ] 4.2 Add `cabinet_ocr_sheet.dart`: capture (camera/gallery) → review
    (opaque detection cards + confirm checkboxes, low-confidence pre-unchecked) →
    import (enabled only when confirm-gate satisfied). Offline blocks capture/
    import; coarse no-PII analytics. Requirement 4.2–4.6.
  - [ ] 4.3 Wire an "Quét nhãn thuốc" action into `cabinet_screen_v3.dart`;
    modernize item cards (glass card chrome, expiry/needs-review status by text),
    preserve consent gate + DDI two-medicine guard + `DdiResultView`. Requirement
    4.1, 5.
  - [ ] 4.4 Cabinet tests: unconfirmed detection ⇒ import disabled ⇒ no import
    call; offline blocks; consent gate blocks CRUD; DDI <2 distinct does not run;
    DDI view hides runtime internals. Requirement 4.4, 4.6, 5.

- [ ] 5. Modernize remaining V3 surfaces
  - [ ] 5.1 Apply glass chrome + squircle cards to PHR, Council, Scribe, Settings,
    Login, More via `GlassSurface`; clinical bodies stay opaque. Reuse all data
    contracts + safety gates. Requirement 5, 7.
  - [ ] 5.2 Regression tests: existing redesign suite still green; new surfaces
    keep no `BackdropFilter` ancestor over clinical text. Requirement 5, 7.

- [ ] 6. Enable full admin feature set (server)
  - [ ] 6.1 Expand `_FEATURE_FLAGS_BY_ROLE['admin']` in `mobile.py` to grant every
    client-consumed key `true` (research, careguard, council, system_monitor,
    chat_mobile_enabled, selfmed_cabinet_mobile_enabled, scribe_mobile_enabled,
    phr_enhanced_mobile_enabled, model_disclosure_mobile_enabled,
    transparency_notice_mobile_enabled, consent_center_mobile_enabled,
    sharing_mobile_enabled, research_mobile_deep, mobile_ux_polish_enabled).
    Other roles unchanged. Requirement 8.
  - [ ] 6.2 pytest: admin emits the complete flag set; non-admin roles untouched;
    RBAC 403 preserved for unauthorized roles. Requirement 8.

- [ ] 7. Quality gates + a11y
  - [ ] 7.1 `flutter analyze` clean (glass + changed files); a11y pass (≥48dp,
    text scaler 1.6×, reduced-motion collapses glass motion, status-by-text).
    Requirement 7.
  - [ ] 7.2 Full redesign + glass test suite green. Requirement 1–5, 7.

- [ ] 8. Server model swap (deepseek-v4)
  - [ ] 8.1 On the server `.env`: set DeepSeek model to `deepseek-v4-pro` with
    fallback `deepseek-v4-flash`, base URL `https://api.yescale.vip` (keys
    unchanged). Restart ML/API; verify `/api/v1/health` + a routed chat. Roll back
    on health failure. Requirement 9.

- [ ] 9. Build, deploy, install
  - [ ] 9.1 Build Android release on the build server (Docker cirruslabs/flutter,
    44-core Gradle) with `MOBILE_REDESIGN_ENABLED=true
    MOBILE_LIQUID_GLASS_ENABLED=true CLARA_API_BASE_URL=https://clara.thiennn.icu`.
    Requirement 10.
  - [ ] 9.2 Pull the APK locally, install on the connected device, launch, and
    confirm the glass Login/Home render (screenshot). Requirement 10.

## Notes

### Requirement → primary task
- R1 (glass system) → 1.1–1.5
- R2 (glass chrome) → 2.1–2.3
- R3 (Home) → 3.1, 3.2
- R4 (OCR) → 4.1, 4.2, 4.4
- R5 (cabinet + surfaces) → 4.3, 5.1
- R6 (fallback) → 1.2, 1.3
- R7 (a11y/contrast) → 5.2, 7.1
- R8 (admin flags) → 6.1, 6.2
- R9 (model swap) → 8.1
- R10 (build/install) → 9.1, 9.2

### Safety invariants (regression-locked)
Glass = chrome only; clinical content always opaque + AA. Consent gate,
emergency fast-path, DDI two-medicine guard, FIDES/CRITICAL blocking, no-PII
telemetry, CSRF, RBAC — all preserved. New gate default OFF.
