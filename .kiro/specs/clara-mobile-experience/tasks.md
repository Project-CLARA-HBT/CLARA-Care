# Implementation Plan: CLARA Mobile Experience (Modern UI/UX)

## Overview

This plan modernizes the Flutter mobile app into a polished, modern, easy-to-use
experience — **additively and behind a single build flag
`MOBILE_EXPERIENCE_V2_ENABLED` (default OFF)**. With the flag off the app is
byte-for-byte unchanged (legacy `ClaraApp` → `DashboardScreen`). Tasks are
ordered so the design system lands first, the adaptive shell wraps it, and the
modern Home + onboarding build on top, with a single writer for `app.dart` that
flips between the legacy and Experience_V2 roots. Every task reuses the existing
`a11y.dart`, `feature_flags.dart`, `analytics.dart`, `ErrorRetryView`, and
`OfflineBanner` rather than re-implementing them.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the existing `apps/mobile/test` harness (`flutter_test`) and `test/fakes`
  (Api_Client, Session_Store, recording analytics transport); keep all current
  tests green.
- Tag property tests `P1..P7` mapping to the design's Correctness Properties.
- A flags-off baseline test asserts the authenticated root is the legacy
  `DashboardScreen` and no Experience_V2 widget is constructed (Property P1).

## Task Dependency Graph

Same-file writers are serialized into different waves to avoid write conflicts:
`feature_flags.dart` (1.2, single writer, before any flag read),
`lib/theme/tokens.dart` (2.1) → `lib/theme/clara_theme.dart` (2.2) → components
(2.3–2.5) → `lib/experience/app_shell.dart` (3.1) → `home_screen.dart` (4.1),
and `app.dart` is written by exactly one task (9.1) after the shell/Home/
onboarding exist. New Experience_V2 files live in disjoint paths and parallelize
freely once the wave they depend on lands.

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5", "6.1"] },
    { "id": 4, "tasks": ["2.6", "3.1", "5.1", "7.1"] },
    { "id": 5, "tasks": ["3.2", "4.1", "5.2", "6.2"] },
    { "id": 6, "tasks": ["3.3", "4.2", "5.3", "8.1"] },
    { "id": 7, "tasks": ["9.1"] },
    { "id": 8, "tasks": ["9.2"] },
    { "id": 9, "tasks": ["4.3", "5.4", "7.2", "8.2"] },
    { "id": 10, "tasks": ["10.1", "10.2", "10.3", "10.4", "10.5"] }
  ]
}
```

## Tasks

- [x] 1. Foundations (flag, test harness, persistence stores)
  - [x] 1.1 Extend the `test/` harness/fakes for Experience_V2 widget tests (fake secure storage, recording analytics transport, width-class pumping helper); keep existing tests green. _Requirements: 10.5, 10.6_
  - [x] 1.2 Add `kMobileExperienceV2Enabled = bool.fromEnvironment('MOBILE_EXPERIENCE_V2_ENABLED', defaultValue: false)` to `lib/core/feature_flags.dart` (single writer; additive, default OFF). _Requirements: 1.1, 1.6_
  - [x] 1.3 Add `lib/experience/onboarding/onboarding_store.dart` and `lib/experience/language_store.dart` over the existing `flutter_secure_storage` (no new dependency), with graceful-degradation defaults. _Requirements: 1.5, 5.3, 9.2_

- [x] 2. Material 3 design system (Req 2)
  - [x] 2.1 Add `lib/theme/tokens.dart` — brand seed color + spacing/radius/elevation/motion duration tokens (single writer; pure constants). _Requirements: 2.2_
  - [x] 2.2 Add `lib/theme/clara_theme.dart` + `lib/theme/typography.dart` — `ClaraTheme.light()/dark()` `ThemeData` from `ColorScheme.fromSeed` (M3), AA-contrast checked, component themes wired to tokens. _Requirements: 2.1, 2.5_
  - [x] 2.3 Add buttons `lib/theme/components/clara_button.dart` (primary/secondary) consuming tokens, honoring text scaling + reduced motion via `A11y`. _Requirements: 2.2, 2.3, 2.4_
  - [x] 2.4 Add `clara_card.dart` + `clara_chip.dart` consuming tokens + A11y semantics. _Requirements: 2.2, 2.3_
  - [x] 2.5 Add `clara_input.dart` + `section_header.dart` consuming tokens; section header marked as a11y header. _Requirements: 2.2, 2.3, 9.3_
  - [x] 2.6 **[Dart widget test]** Theme/components: tokens applied, dynamic text scaling honored (no clip), light/dark resolve from brightness. _Requirements: 2.1, 2.3, 2.5_

- [x] 3. Adaptive app shell (Req 3)
  - [x] 3.1 Add `lib/experience/app_shell.dart` — `NavigationBar` (compact) / `NavigationRail` (medium/expanded) by 600dp breakpoint; holds `selectedIndex`; nav controls wrap `MinTapTarget` + `A11yLabeled`; transitions via `A11y.resolveMotionDuration`. _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 3.2 **[Dart widget test]** Shell renders bottom nav under phone width and rail under tablet width; selected index preserved across width/orientation change. _Requirements: 3.1, 3.2_
  - [x] 3.3 **[Dart widget test]** Shell nav controls expose semantics + meet ≥48dp; reduced motion collapses nav transition to instant (Property P3, P2). _Requirements: 3.3, 3.4_

- [x] 4. Modern role-aware Home (Req 4)
  - [x] 4.1 Add `lib/experience/home_screen.dart` — greeting, quick-action `ClaraCard`s, recent-items region; load `mobile/summary` and gate via existing `MobileFeatureFlagResolver` (same semantics as `DashboardScreen`); PHR always present. _Requirements: 4.1, 4.2, 4.5_
  - [x] 4.2 Wire Home fail-closed behavior: summary-load failure ⇒ no privileged quick actions + `ErrorRetryView` retry; never derive admin-only surfaces for non-admin. _Requirements: 4.3, 4.4_
  - [x] 4.3 **[Dart widget test]** Home loading skeleton / success / empty / fail-closed error; non-admin never sees admin surfaces (Property P4). _Requirements: 4.2, 4.3, 4.4, 4.5_

- [x] 5. First-run onboarding & priming (Req 5)
  - [x] 5.1 Add `lib/experience/onboarding/onboarding_carousel.dart` — skippable paged intro + permission/consent priming copy (Vietnamese-first); paging animation via `A11y`. _Requirements: 5.1, 5.2, 5.4_
  - [x] 5.2 Persist "onboarding seen" via `OnboardingStore` on complete/skip; emit coarse no-PII analytics event through the shared client. _Requirements: 5.3, 5.5_
  - [x] 5.3 **[Dart widget test]** Onboarding shows on first run, skip + completion persist "seen" so it does not reappear (Property P5). _Requirements: 5.1, 5.3, 5.6_
  - [x] 5.4 **[Dart widget test]** Onboarding controls expose semantics + ≥48dp; reduced motion collapses carousel animation to instant (Property P2, P3). _Requirements: 5.4_

- [x] 6. Polished states (Req 6)
  - [x] 6.1 Add `lib/experience/states/` — `skeleton.dart`, `empty_state.dart` (Vietnamese-first), `success_snackbar.dart`; reuse `ErrorRetryView`/`OfflineBanner` for error/offline. _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [x] 6.2 Apply pull-to-refresh (`RefreshIndicator`) + skeleton/empty/success/error wiring on Home and the shell's primary scrollable surfaces. _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 7. Micro-interactions & transitions (Req 7)
  - [x] 7.1 Add `lib/experience/states/motion.dart` — `ClaraPageTransitionsBuilder` + card-press/list-reveal helpers resolving durations through `A11y.resolveMotionDuration`; input never blocked. _Requirements: 7.1, 7.3_
  - [x] 7.2 **[Dart widget test]** Page/card/list animations collapse to `Duration.zero` under reduced motion; functional state changes still occur (Property P2). _Requirements: 7.2, 7.3_

- [x] 8. Branding & language toggle + a11y (Req 8, 9)
  - [x] 8.1 Add `lib/experience/language_controller.dart` (vi default, app-wide, persisted via `LanguageStore`) + a Settings language toggle; emit coarse no-PII event on change. _Requirements: 9.1, 9.2, 9.6_
  - [x] 8.2 Document branding (display name, adaptive launcher icon, themed splash) in `apps/mobile/README.md`/`docs/branding.md`: manifest/plist keys, asset sizes, optional/manual generator packages; commit NO binaries; preserve launch hydration (no artificial delay). _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 9. App wiring (single writer for app.dart / main.dart)
  - [x] 9.1 In `lib/app.dart` (single writer) branch the authenticated root on `kMobileExperienceV2Enabled`: false ⇒ legacy `DashboardScreen` unchanged; true ⇒ `ClaraTheme` + onboarding-gate + `AppShell`(Home/Tools/Record/Settings). Preserve hydration + `ConsentGate`. _Requirements: 1.1, 1.2, 1.3, 2.1, 2.6, 3.5, 4.6, 5.6_
  - [x] 9.2 In `lib/main.dart` (single writer) construct `LanguageController` and apply `MaterialApp` locale when V2 is on; legacy locale path unchanged when off. _Requirements: 9.1, 9.2_

- [x] 10. Final quality-gate checkpoint
  - [x] 10.1 **[PBT]** Flags-off equivalence: with `MOBILE_EXPERIENCE_V2_ENABLED` false, authenticated root is legacy `DashboardScreen` and no Experience_V2 widget is constructed; reachable navigation equals baseline (Property P1). _Requirements: 1.1, 1.2, 1.3, 10.1_
  - [x] 10.2 **[PBT]** No-PII analytics: every Experience_V2 event (home viewed, onboarding completed/skipped, language changed) passes the redaction projection at any nesting depth (Property P7). _Requirements: 9.6, 10.4_
  - [x] 10.3 **[Dart widget test]** Full Experience_V2 happy path with flag on: onboarding → shell → Home renders without exceptions across phone + tablet widths. _Requirements: 10.2_
  - [x] 10.4 Language persistence + default test: defaults to Vietnamese; persisted selection round-trips across restart and applies app-wide (Property P6). _Requirements: 9.1, 9.2_
  - [x] 10.5 `flutter analyze` clean; full `flutter test` green (new P1–P7 + widget tests; existing analytics/a11y/feature-flag/session-store tests still pass). _Requirements: 10.5, 10.6_

## Notes

### Property → implementing test task
- P1 (flags-off equivalence) → 10.1
- P2 (reduced-motion collapse) → 3.3, 5.4, 7.2
- P3 (a11y invariants) → 2.6, 3.3, 5.4
- P4 (Home fail-closed gating) → 4.3
- P5 (onboarding persistence) → 5.3
- P6 (language persistence & default) → 10.4
- P7 (no-PII analytics) → 10.2

### Single-writer files (serialized across waves)
- `lib/core/feature_flags.dart` → 1.2 only.
- `lib/theme/tokens.dart` → 2.1 only (before 2.2 and components).
- `lib/theme/clara_theme.dart` → 2.2 only.
- `lib/experience/app_shell.dart` → 3.1 only (before Home consumes it).
- `lib/experience/home_screen.dart` → 4.1 only (fail-closed wiring 4.2 extends it same wave-after).
- `lib/app.dart` → 9.1 only. `lib/main.dart` → 9.2 only.

### Staged enablement
1. Internal/dev builds with `--dart-define=MOBILE_EXPERIENCE_V2_ENABLED=true` for QA of shell/Home/onboarding.
2. Branding assets generated locally (optional packages) and verified per platform.
3. Production enablement of `MOBILE_EXPERIENCE_V2_ENABLED` once flags-off equivalence (P1), a11y (P3), and no-PII (P7) gates are green.

### Subagent assignment guidance
- Design system (task 2) — one writer (tokens → theme → components ordering).
- Shell + Home (tasks 3, 4) — sequential single writer (shell before Home).
- Onboarding + polished states + motion (tasks 5, 6, 7) — disjoint writers, parallelizable.
- App wiring (task 9) — one writer, last before the quality gate.
