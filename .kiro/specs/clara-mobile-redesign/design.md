# Design Document

CLARA Mobile Redesign — a ground-up rebuild of the Flutter client
(`apps/mobile`) to reach visual and functional parity with CLARA_Web, behind a
single additive experience gate.

## Overview

The mobile app today ships two parallel experiences behind
`kMobileExperienceV2Enabled` (default **OFF**): a legacy teal-seed
`DashboardScreen`, and an "Experience_V2" adaptive shell that is well-factored
but incomplete and dark by default. Individual feature surfaces sit at two
visual maturity tiers — a **polished tier** (Chat, Consent Center) built on the
`ClaraTokens` design system with `a11y` helpers and semantics, and a
**prototype tier** (Home, Login, Research, Council, both cabinets, PHR, Scribe,
Auth flows) using raw Material widgets, `OutlineInputBorder`, and hardcoded
status colors.

This redesign delivers a cohesive, modern, web-parity experience across every
surface. It is **additive and reversible**: all new work lands behind a single
compile-time gate, `MOBILE_REDESIGN_ENABLED`, that defaults OFF. When the gate
is off, the app is byte-for-byte the current experience. When on, the app
presents the redesigned shell, home, settings, and feature surfaces.

The redesign reuses — never rewrites — the existing `ApiClient`,
`SessionStore`, `MobileFeatureFlagResolver`, `Analytics` (no-PII), consent
gating, `a11y`, and connectivity/offline infrastructure. It changes **no**
CLARA_API contract and preserves every safety guardrail (RBAC, consent gating,
emergency fast-path, no-PII telemetry, mandatory clinician-review directives,
DDI two-medicine guard, never-fabricate-all-clear).

### Design principles

1. **Web is the north star.** Palette, type rhythm, information architecture,
   and surface completeness track CLARA_Web. The mobile app should feel like
   the same product, adapted to touch.
2. **Light-first, system-capable.** Default `ThemeMode.light`; users can switch
   to dark or follow the OS from Settings.
3. **One design system.** Every surface reads from `ClaraTokens` +
   `WebPalette` + shared components. No hardcoded hex, no raw `OutlineInputBorder`.
4. **Center-stage Chat.** A circular, elevated Chat action anchors the center
   of the bottom navigation bar — Chat is the product's primary entry point.
5. **Safety and accessibility are invariants**, not features. Preserve all
   guardrails and every `a11y` hook (text scaling, reduced motion, ≥48dp
   targets, semantics).

## Scope & gating

### The single experience gate

```dart
// lib/core/feature_flags.dart (additive)
const bool kMobileRedesignEnabled = bool.fromEnvironment(
  'MOBILE_REDESIGN_ENABLED',
  defaultValue: false,
);
```

`app.dart` selects the redesigned root only when `kMobileRedesignEnabled` is
true. Off ⇒ the existing `kMobileExperienceV2Enabled` / legacy branch is chosen
exactly as today. This is a strict superset: the redesign gate is checked
*before* the V2 gate, and only rewrites the authenticated-root construction and
the `MaterialApp` `themeMode`.

Per-feature availability continues to flow through the existing
`MobileFeatureFlagResolver` (server `mobile/summary` flags combined with
build-time `--dart-define` defaults). The redesign does **not** introduce new
per-feature gates; it re-skins and completes the surfaces that those existing
gates already control, and always renders the same fail-closed inert/placeholder
states when a gate is off.

### Light-mode default

`MaterialApp.themeMode` is currently unset (⇒ `ThemeMode.system`). The redesign
sets `themeMode` from a new persisted preference (default `ThemeMode.light`),
read at launch from a `ThemePreferenceStore` (secure-storage seam, mirroring
`LanguageStore`). Settings exposes Light / Dark / System.

## Architecture

### Root composition (`app.dart`)

```
ClaraApp
  └─ (kMobileRedesignEnabled?)
       ├─ yes → RedesignedApp
       │          MaterialApp(
       │            theme: ClaraTheme.light(polished: true),
       │            darkTheme: ClaraTheme.dark(polished: true),
       │            themeMode: <from ThemePreferenceController>,
       │            locale: <from LanguageController>,
       │          )
       │          home → hydration → ConsentGate → RedesignShell
       └─ no  → existing V2 / legacy MaterialApp (unchanged)
```

`RedesignShell` replaces the 4-destination `AppShell` with a
center-Chat-anchored bottom navigation on compact widths and a
`NavigationRail` on medium/expanded widths (preserving the existing adaptive
breakpoint of 600dp and the selection-preserved-across-relayout guarantee).

### Navigation model

Compact (phone) — a `Scaffold` with a custom bottom bar:

```
┌───────────────────────────────────────────────┐
│                  <active body>                  │
│                                                 │
├───────────────────────────────────────────────┤
│   Trang chủ   Tủ thuốc   (●Chat)  Hồ sơ  Thêm   │
└───────────────────────────────────────────────┘
                        ▲
             circular, raised, brand-filled
             FAB-style center action (Chat)
```

- The center Chat action is a raised circular button (a `FloatingActionButton`
  docked via `FloatingActionButtonLocation.centerDocked` over a
  `BottomAppBar` with a notch, OR a custom bar with an overlapping circular
  button). It is always present and always routes to Chat; when
  `chat_mobile_enabled` is off for the role, it routes to a friendly inert
  Chat placeholder (never hidden — Chat is the anchor).
- Four flanking destinations: **Trang chủ** (Home), **Tủ thuốc** (Medicine
  cabinet), **Hồ sơ** (PHR), **Thêm** (More). "Thêm" opens a sheet/section
  listing the remaining role-gated surfaces (Research is unified into Chat on
  web, so on mobile the "research" affordance lives inside Chat's mode
  selector; Council, Scribe, CareGuard interaction check, Consent Center,
  Shared resources, Settings, Help live under More or their home cards).

Medium/expanded — a `NavigationRail` with the same destinations (Chat as a
prominent top rail item), body in an `Expanded` region.

Selection lives in `State` (not derived from width) so it survives
resize/rotation, exactly as the current `AppShell`.

### Information architecture (parity with web)

| Web nav item | Mobile placement | Existing gate |
|---|---|---|
| Chat (`/chat`, fast/deep/deep_beta) | Center anchor action | `chat_mobile_enabled`; deep modes `research_mobile_deep` |
| Dashboard / Tổng quan | Home tab (role-aware) | always (role-scoped summary) |
| PHR (`/phr`) | Hồ sơ tab | always; enhanced `phr_enhanced_mobile_enabled` |
| Tủ thuốc (`/selfmed`) | Tủ thuốc tab (primary) | `selfmed_cabinet_mobile_enabled` |
| Kiểm tra tương tác (`/careguard`) | Inside Tủ thuốc (DDI action) + More | `careguard` |
| Hội chẩn AI (`/council`) | More → Council | `council` (+`council_mobile_parity`) |
| Medical Scribe (`/scribe`) | More → Ghi chú | `scribe_mobile_enabled` + doctor |
| Nguồn nghiên cứu (`/research/source-hub`) | Inside Chat deep-mode context (deferred; see Non-Goals) | `research` |
| Consent / Data | More → Quyền riêng tư | `consent_center_mobile_enabled` |
| Hướng dẫn (`/huong-dan`) | More → Trợ giúp | always |
| Settings | More → Cài đặt | always |

This mirrors the web's grouping (core / medication / clinical / support) while
respecting mobile's limited primary-nav slots by promoting the three most-used
surfaces (Home, Tủ thuốc, Hồ sơ) plus Chat to the bar, and collecting the rest
under More.

## Design system

### Theme

Both redesigned themes are built with `polished: true`, so they use
`webColorScheme(brightness)` (the explicit, AA-verified web palette) rather than
the teal seed. This is the key visual change that makes mobile match web. The
existing `ClaraTheme._build` already supports this path; the redesign flips it
on unconditionally for the redesigned root and does not alter the token-driven
component themes (card/button/input/chip/nav/appbar/dialog/sheet).

Palette (from `WebPalette`, already ported from `apps/web/styles/globals.css`):

- **Light**: canvas `#F7F9FB`, surface `#FFFFFF`, primary/action `#2563EB`
  (brand-600), text `#1F2937`, muted `#4B5563`, soft-brand container `#DBEAFE`.
- **Dark**: canvas `#111A2D`, surface `#1D2840`, primary `#2563EB`, text
  `#DAE2FD`.
- **Status** via `ClaraStatusColors` extension (success/warning) + scheme
  `error`, always paired with icon + text (never color alone).

### Tokens

Reuse `ClaraTokens` (spacing 4/8/16/24/32, radius 8/12/20, elevation 0/1/3/6,
motion 120/240/400ms base). The redesign may add a small number of tokens if a
surface genuinely needs them (e.g., a `radiusXl = 28` to match web's `--radius-xl`
for hero cards, and an `avatarSize`/`fabSize` constant for the center Chat
action). Any addition is documented inline and covered by the design-token test.

### Components

Reuse and extend the existing `lib/theme/components/` library
(`ClaraButton`, `ClaraCard`, `ClaraChip`, `ClaraInput`, `SectionHeader`). New
shared components introduced by the redesign, all token-driven, a11y-first,
Vietnamese-first copy at call sites:

- **`ClaraScaffold`** — a standard screen scaffold (app bar with back affordance,
  scroll-under elevation, optional actions, consistent body padding, offline
  banner slot) so every feature surface shares chrome.
- **`ClaraCenterNavBar`** — the custom bottom bar with the docked circular Chat
  action + flanking destinations. Guarantees ≥48dp targets and single-label
  semantics (mirroring the current `AppShell` icon/label discipline).
- **`ClaraListTileCard`** — the tappable card used for Home tool cards and More
  entries (icon, title, subtitle, trailing chevron/status), replacing raw
  `ListTile`/`_QuickActionCard`.
- **`ClaraStatCard`** — compact metric card for the role-aware Home/Dashboard
  (counts/distributions only — no PII).
- **`ClaraFormField`** — thin wrapper over `ClaraInput` adding label + helper +
  error rows consistently for the auth/forms surfaces.
- **`ClaraSegmented`** — a themed segmented control (for Chat modes, Settings
  theme choice) replacing bare `SegmentedButton` styling.
- **`ClaraEmptyState`/`ErrorRetryView`/`ClaraSkeletonList`/`OfflineBanner`** —
  reuse existing state widgets unchanged.

### Motion & accessibility

All motion resolves through `A11y.resolveMotionDuration` (collapses to zero
under reduced motion). All tap targets ≥48dp via `MinTapTarget`. Text scaling
honored via `A11y.resolveTextScaler`. Semantics: headers via
`A11yLabeled(isHeader)`, buttons via button semantics, live regions for
streaming (Chat), single-announcement nav labels. AA contrast is guaranteed by
`webColorScheme` (already property-tested) and re-verified for any new pairing.

## Surface-by-surface design

### Home / Dashboard (Trang chủ)

Rebuild `home_screen.dart` as a modern, role-aware landing:

- **Greeting header** — time-of-day greeting + role chip (no PII beyond the
  email the app already shows; keep it optional/subtle).
- **Quick stats row** (role-aware, from `mobile/summary`, counts only) —
  `ClaraStatCard`s (e.g., cabinet item count, recent activity count). Admin sees
  a system-health stat only when `system_monitor` is granted (fail-closed).
- **Primary tools grid** — `ClaraListTileCard`s for the role's enabled surfaces,
  derived from the same resolver as today (fail-closed on unloaded summary),
  with skeleton on first load and `ErrorRetryView` on failure.
- **Recent activity** — real recents where an endpoint exists (e.g., latest
  council case, recent scribe sessions for doctors), otherwise the existing
  friendly empty state. No fabricated data.
- Pull-to-refresh + offline banner (wire the `ConnectivityService` the current
  Home TODO notes is missing).

### Chat (center anchor)

Reuse the already-polished `ChatScreen` / `PolishedChatView` / `chat_*` widgets
essentially as-is (they are the reference tier). Redesign work is limited to:

- Hosting Chat as the center-anchor destination with its own app bar.
- Ensuring the mode selector (`fast` / `deep` / `deep_beta`) uses
  `ClaraSegmented` and that deep modes remain gated by `research_mobile_deep`.
- Keeping the standing medical disclaimer, emergency banner/fast-path, offline
  gating, and no-PII analytics intact.

### Tủ thuốc (Medicine cabinet, primary tab)

This is the surface the user most wants elevated. Design a first-class personal
medicine cabinet consolidating today's `selfmed_cabinet_screen.dart` and the
in-cabinet DDI from `careguard_cabinet_screen.dart`:

- **Cabinet list** — `ClaraCard` per medicine showing name, active ingredient
  (normalization status / needs-review chip), dose, form, quantity, and expiry
  with a **near-expiry / expired** visual state (status color + icon + text).
- **Add / edit** — a polished bottom-sheet editor (`ClaraFormField`s for
  drug/brand/manufacturer/dose/form/quantity/expiry/note), consent-gated exactly
  as today, 409-duplicate handling preserved.
- **Interaction check (DDI)** — a prominent action that runs the analyze call on
  cabinet contents, preserving the **≥2 distinct-medicine guard**, the End_User
  DDI projection (`DdiResultView` — hides mode/fallback/source_errors), the
  never-fabricate-all-clear rule, and offline stale-cache behavior.
- **Empty / offline / consent** states all use shared widgets.
- Existing gates preserved: `selfmed_cabinet_mobile_enabled` for CRUD,
  `careguard` for the DDI action; both off ⇒ inert placeholders.

Where the current app has two overlapping cabinet screens, the redesign
presents **one** cabinet experience and routes the legacy screens' capabilities
into it, without removing the underlying API calls or gates.

### Hồ sơ (PHR)

Rebuild `phr_screen.dart`'s presentation (it is the largest, form-heavy screen)
into card-grouped sections (basic info, allergies, conditions, medications,
emergency card) with inline edit and a clear save affordance. Preserve the
controller-bound model, the full `updatePhrRecord` payload, no-PII analytics
(entry-count only), and the `phr_enhanced_mobile_enabled` gate for
export/emergency-card affordances.

### Hội chẩn AI (Council)

Re-skin the case-based wizard (`council_case_screen.dart`) as the primary flow
(intake → specialists → result) using shared components and a clear step
indicator, making it "dễ sử dụng hơn." Preserve the phase state machine, the
mandatory clinician-review directive on every result, no-PII analytics, and the
`council` + `council_mobile_parity` gating (legacy `CouncilScreen` remains the
fallback when parity is off).

### Ghi chú (Scribe)

Re-skin `scribe_screen.dart` (session list, detail, consent capture, transcript
append, audio upload where an `audioProvider` is injected, SOAP regenerate,
status). Preserve the three fail-closed gating layers (flag → doctor RBAC →
per-session consent), `stripTelemetryLabels` on clinical text, and content-free
analytics.

### Auth (Login, Register, Verify, Forgot, Reset)

Re-skin all five surfaces with `ClaraScaffold`/`ClaraFormField`/`ClaraButton`:
brand header, proper field validation, show/hide password toggle,
confirm-password on register/reset, and consistent success/error/info states.
No API-contract change; keep anti-enumeration neutrality on forgot-password and
the register consent checkboxes.

### Settings (Cài đặt)

A real settings surface (replacing the placeholder):

- **Appearance** — theme mode (Light / Dark / System) via `ClaraSegmented`,
  persisted through `ThemePreferenceController`.
- **Language** — the existing `LanguageToggle` (vi/en).
- **Account** — email display, sign-out.
- **Privacy & data** — entry to Consent Center / DSAR when
  `consent_center_mobile_enabled` is on.
- **About** — app version, model disclosure chips (when
  `model_disclosure_mobile_enabled`), AI transparency notice (when
  `transparency_notice_mobile_enabled`), links to Help/legal.

### More (Thêm)

A sheet/section listing the role-gated surfaces not on the primary bar
(Council, Scribe, DDI check, Consent Center, Shared resources, Help, Settings),
each a `ClaraListTileCard`, gated by the same resolver, with inert entries
hidden (not shown-disabled) except where a placeholder communicates a
role/flag restriction, matching current fail-closed behavior.

## New/changed files (planned)

Additive-first. New:

- `lib/core/theme_preference_store.dart`, `lib/experience/theme_preference_controller.dart`
- `lib/experience/redesign/redesign_shell.dart` (center-nav shell)
- `lib/theme/components/clara_scaffold.dart`, `clara_center_nav_bar.dart`,
  `clara_list_tile_card.dart`, `clara_stat_card.dart`, `clara_form_field.dart`,
  `clara_segmented.dart`
- `lib/experience/redesign/home_redesigned.dart`, `settings_screen.dart`,
  `more_sheet.dart`, `medicine_cabinet_screen.dart` (unified)
- Tests co-located under `test/` mirroring existing structure.

Changed (gated so flag-off is unchanged):

- `lib/core/feature_flags.dart` — add `kMobileRedesignEnabled`.
- `lib/app.dart` — add the redesign root branch + `themeMode` wiring.
- `lib/theme/tokens.dart` — optional additive tokens (radiusXl, fab/avatar sizes).
- `lib/main.dart` — construct `ThemePreferenceController` (load before first
  frame) only on the redesign path.

Existing feature screens (`chat_*`, `phr_screen`, `council_case_screen`,
`scribe_screen`, cabinets, auth) are re-skinned in place or wrapped; their API
calls, gating, and safety logic are preserved.

## Data & API

No CLARA_API contract changes. All surfaces use the existing `ApiClient`
methods (chat/stream, research tier2 + jobs SSE, careguard analyze + cabinet
CRUD, council cases, scribe sessions/transcribe/consent, phr get/update, mobile
summary, auth). Session/refresh/401-retry via `SessionStoreAuthHooks` unchanged.

## Safety & privacy invariants (regression-locked)

- **RBAC & fail-closed gating** — unloaded/absent summary ⇒ no privileged
  surface; Scribe requires doctor; admin surfaces require `system_monitor`.
- **Consent gating** — medical CRUD (cabinet, selfmed, scribe per-session)
  stays consent-gated; the app-level `ConsentGate` still precedes the shell.
- **Emergency fast-path** — Chat emergency detection/banner preserved.
- **DDI discipline** — ≥2 distinct-medicine guard; End_User projection hides
  runtime internals; never fabricate an all-clear; offline stale cache labeled.
- **No-PII telemetry** — analytics remain counts/booleans; clinical text is
  never sent; `stripTelemetryLabels` on scribe/research surfaces.
- **Clinician-review directive** — council results always carry it.
- **Offline** — mutations blocked offline where they are today; stale reads
  labeled.

## Testing strategy

Mirror the repo's Flutter widget + pure-unit test pattern. Key properties:

- **P1 — Flag-off equivalence.** With `kMobileRedesignEnabled` off, the root,
  theme, and navigation are byte-for-byte the current behavior (widget test
  asserting the legacy/V2 branch renders and no redesign widget is built).
- **P2 — Light-mode default.** With the redesign on and no stored preference,
  `MaterialApp.themeMode == ThemeMode.light`; changing it persists and reapplies.
- **P3 — Center Chat anchor always present.** The center action renders and
  routes to Chat (or its inert placeholder when `chat_mobile_enabled` is off),
  regardless of role/flags.
- **P4 — Fail-closed gating parity.** For every surface, a null/unloadable
  summary yields the same inert/placeholder state as today and issues zero
  privileged API calls.
- **P5 — Safety invariants.** DDI two-medicine guard, never-fabricate-all-clear,
  emergency fast-path, clinician-review directive, consent gates, and
  no-PII analytics each have a preserved/added test.
- **P6 — AA contrast.** The redesigned theme's on-color pairings clear WCAG AA
  (extends the existing `web_palette` contrast property to any new pairing).
- **P7 — a11y.** ≥48dp targets, single-label nav semantics, reduced-motion
  collapse, and text-scaler tolerance on the new components.

Every task is verifiable with `flutter analyze` and `flutter test` in
`apps/mobile`.

## Non-Goals

- No CLARA_API/backend changes.
- No new runtime dependencies unless a task explicitly justifies one (e.g., an
  audio-recorder plugin is **out of scope**; Scribe audio stays behind the
  injected `audioProvider` seam as today).
- Full "Nguồn nghiên cứu" source-hub browser parity on mobile is **deferred**;
  the redesign surfaces research through Chat's deep modes (matching web's
  unification of research into Chat) and leaves a documented entry point for a
  later source-hub task.
- Removing the legacy/V2 code paths is deferred to a later cleanup once the
  redesign is default-on and parity is verified.
