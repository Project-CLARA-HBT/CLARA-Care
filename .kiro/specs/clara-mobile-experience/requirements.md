# Requirements Document

## Introduction

This feature modernizes the **CLARA-Care Flutter mobile app** (`apps/mobile/*`)
from its functional-but-flat starter UI into a **polished, modern, easy-to-use,
best-in-market experience**: a cohesive Material 3 design system, an adaptive
app shell (bottom navigation on phones, navigation rail on tablets/large
screens), a modern role-aware Home, first-run onboarding, consistently polished
states (skeletons, empty states, success confirmations, error/offline), tasteful
micro-interactions, refreshed branding, and a global language toggle — all while
meeting AA accessibility.

The work is **additive, back-compatible, and gated behind a single build/server
flag `MOBILE_EXPERIENCE_V2_ENABLED` (default OFF)**. When the flag is off, the
app is **byte-for-byte unchanged**: it boots through the existing
`ClaraApp` → `DashboardScreen` path, with the same theme, navigation, screens,
and CLARA_API calls as today. The flag does not gate any backend behavior; it
selects between the legacy surfaces and the new experience purely on the client.

This feature **reuses** the existing core modules rather than replacing them:
the accessibility primitives in `lib/core/a11y.dart` (dynamic text scaling,
reduced-motion resolver, semantics helpers, ≥48dp targets), the additive
feature-flag pattern in `lib/core/feature_flags.dart` (build-time
`--dart-define` defaults that fail closed), and the consent- and PII-guarded
analytics facade in `lib/core/analytics.dart`. It also reuses the existing
resilience widgets `ErrorRetryView` and `OfflineBanner`.

It introduces **no new pubspec plugin dependencies**: persistence for
"onboarding seen" and the language preference reuses the already-present
`flutter_secure_storage`. Where an adaptive launcher icon or themed splash would
normally be produced with a generator package (e.g. `flutter_launcher_icons` /
`flutter_native_splash`), this feature **documents** the asset/manifest steps and
keeps the package optional/manual so no large binaries are committed and no new
dependency is forced.

CLARA-Care remains **decision-support software over self-declared data — not a
medical device and not an EMR/EHR**. Nothing here changes that positioning;
existing disclaimers and safety framing are preserved on every modernized
surface. All copy is **Vietnamese-first** with bilingual vi/en where a term of
art requires it, and **no PII is ever added to analytics**.

## Glossary

- **Mobile_App**: The CLARA-Care Flutter client under `apps/mobile/`.
- **Experience_V2**: The modernized UI/UX introduced by this feature: design system, adaptive shell, modern Home, onboarding, polished states, micro-interactions, branding, and language toggle.
- **Experience flag**: The single build/server switch `MOBILE_EXPERIENCE_V2_ENABLED`, read at compile time via `--dart-define` (`bool.fromEnvironment`, default `false`), that selects Experience_V2 vs. the legacy surfaces.
- **Legacy path / off path**: The current `ClaraApp` → `DashboardScreen` flow and `ThemeData(seedColor: teal)` theme that ship when the Experience flag is off.
- **Design system**: The Material 3 theme (light + dark), brand seed color, typography scale, spacing/radius tokens, and reusable components under `lib/theme/`.
- **Design tokens**: Named spacing, radius, elevation, and duration constants that components and screens consume instead of hard-coded values.
- **App shell**: The adaptive navigation scaffold that wraps the primary surfaces — bottom navigation on compact (phone) widths, navigation rail on medium/expanded (tablet/large) widths.
- **Home**: The modern landing surface (greeting, quick-action cards, recent items) that replaces the flat list `DashboardScreen` when Experience_V2 is on; role-aware via the same `mobile/summary` gating the dashboard uses.
- **Onboarding**: The first-run carousel plus permission/consent priming, skippable and persisted as "seen".
- **Polished states**: Skeleton loaders, friendly empty states, success confirmations, and consistent error/offline states (reusing `ErrorRetryView`/`OfflineBanner`) with pull-to-refresh.
- **Micro-interactions**: Tasteful transitions/animations (page transitions, card press, list reveal) that collapse to instant under reduced motion.
- **A11y module**: The existing `lib/core/a11y.dart` providing reduced-motion resolution, dynamic text-scaling clamp, semantics wrappers, and the ≥48dp tap-target wrapper.
- **Reduced motion**: The OS "remove animations" / accessible-navigation preference resolved by `A11y.prefersReducedMotion`; non-essential animation collapses to `Duration.zero`.
- **Language toggle**: A global vi/en switch whose selection is persisted and applied app-wide, defaulting to Vietnamese.
- **No-PII analytics**: The existing rule that analytics events carry no names, contact info, free-text, or medical content and identify users only by an opaque pseudonymous id.

## Requirements

### Requirement 1: Single-Flag Gating & Back-Compatibility

**User Story:** As a platform operator, I want the entire modernization behind one default-off switch, so that adoption is risk-free and the current app is preserved exactly until we choose to enable it.

#### Acceptance Criteria

1. THE Mobile_App SHALL gate every Experience_V2 surface behind the single flag `MOBILE_EXPERIENCE_V2_ENABLED`, resolved at build time via `--dart-define` with a default of `false`.
2. WHERE `MOBILE_EXPERIENCE_V2_ENABLED` is false, THE Mobile_App SHALL boot through the existing `ClaraApp` → `DashboardScreen` path with the existing theme, navigation, screens, and CLARA_API calls unchanged.
3. WHERE `MOBILE_EXPERIENCE_V2_ENABLED` is false, THE Mobile_App SHALL render no Experience_V2 surface (no app shell, no modern Home, no onboarding) and SHALL keep the legacy surfaces reachable exactly as today.
4. THE Mobile_App SHALL NOT change any CLARA_API contract; Experience_V2 SHALL be achieved through additive client code only.
5. THE Mobile_App SHALL introduce no new pubspec plugin dependency; persistence SHALL reuse the already-present `flutter_secure_storage`.
6. THE Mobile_App SHALL keep the existing `lib/core/a11y.dart`, `lib/core/feature_flags.dart`, and `lib/core/analytics.dart` contracts unchanged, extending them only additively.

### Requirement 2: Material 3 Design System

**User Story:** As a user, I want a cohesive, modern visual design, so that the app feels polished and trustworthy.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled, THE Mobile_App SHALL apply a Material 3 `ThemeData` built from a brand seed color, providing both a light and a dark theme that follow the OS brightness.
2. THE design system SHALL define a typography scale and spacing/radius/elevation tokens under `lib/theme/`, and reusable components (primary/secondary buttons, cards, chips, inputs, section headers) SHALL consume those tokens rather than hard-coded values.
3. THE reusable components SHALL honor the OS dynamic text-scaling preference via the A11y module without clipping primary content or controls.
4. THE reusable components SHALL suppress non-essential animation when reduced motion is requested, resolving durations through the A11y module.
5. THE design system SHALL meet AA contrast for text and essential UI in both light and dark themes.
6. WHERE Experience_V2 is disabled, THE Mobile_App SHALL apply the existing legacy theme unchanged and SHALL NOT load the design system.

### Requirement 3: Adaptive App Shell

**User Story:** As a user, I want navigation that adapts to my device, so that the app is comfortable on both phones and tablets.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled, THE Mobile_App SHALL wrap the primary surfaces in an adaptive shell that presents bottom navigation on compact (phone) widths and a navigation rail on medium/expanded (tablet/large) widths.
2. THE app shell SHALL expose the primary destinations (e.g., Home, Tools, Record, Settings) and SHALL preserve the selected destination across orientation/width changes.
3. THE app shell SHALL provide screen-reader semantics and ≥48dp touch targets for every navigation control, with a logical focus order.
4. THE app shell SHALL apply navigation transitions that collapse to instant under reduced motion.
5. WHERE Experience_V2 is disabled, THE Mobile_App SHALL NOT render the app shell and SHALL keep the legacy `DashboardScreen` navigation.

### Requirement 4: Modern Role-Aware Home

**User Story:** As a user, I want a welcoming home screen that surfaces what matters, so that I can get to my tools quickly.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled, THE Mobile_App SHALL present a modern Home with a greeting, quick-action cards, and a recent-items region, replacing the flat list `DashboardScreen`.
2. THE Home SHALL derive available tools from the `feature_flags` returned by `GET /api/v1/mobile/summary` for the authenticated role, using the same gating semantics as the legacy dashboard.
3. WHEN the role-scoped summary cannot be loaded, THE Home SHALL fail closed (show no privileged quick actions) and SHALL present a retry affordance.
4. THE Home SHALL never expose admin-only surfaces to non-admin roles.
5. THE Home SHALL keep Personal Health Record reachable for every authenticated role, consistent with backend RBAC.
6. WHERE Experience_V2 is disabled, THE Mobile_App SHALL render the legacy `DashboardScreen` unchanged.

### Requirement 5: First-Run Onboarding & Priming

**User Story:** As a first-time user, I want a brief introduction and clear permission context, so that I understand CLARA before granting access.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled AND onboarding has not been seen, THE Mobile_App SHALL present a skippable onboarding carousel introducing CLARA's purpose and decision-support-only positioning.
2. THE onboarding SHALL prime relevant permissions/consent (explaining why, before any system prompt) without itself granting consent.
3. WHEN the user completes or skips onboarding, THE Mobile_App SHALL persist an "onboarding seen" flag via `flutter_secure_storage` and SHALL NOT show onboarding again on subsequent launches.
4. THE onboarding SHALL provide screen-reader semantics, ≥48dp controls, and SHALL collapse carousel/transition animation to instant under reduced motion.
5. THE onboarding SHALL emit only no-PII analytics events (e.g., a coarse "onboarding completed/skipped" event) and SHALL transmit nothing without analytics consent.
6. WHERE Experience_V2 is disabled, THE Mobile_App SHALL NOT present onboarding.

### Requirement 6: Polished States Everywhere

**User Story:** As a user, I want every screen to handle loading, empty, success, and error gracefully, so that the app feels reliable.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled, THE Mobile_App SHALL show skeleton loaders for in-flight data surfaces instead of bare spinners or blank screens.
2. THE Mobile_App SHALL show friendly, Vietnamese-first empty states with guidance when a data surface has no items.
3. THE Mobile_App SHALL show a clear success confirmation after a successful mutating action.
4. THE Mobile_App SHALL present a consistent, non-PII error/offline state on every data surface by reusing the existing `ErrorRetryView` and `OfflineBanner` widgets, with a retry affordance.
5. THE Mobile_App SHALL support pull-to-refresh on primary scrollable surfaces.
6. WHERE Experience_V2 is disabled, THE Mobile_App SHALL retain the legacy states unchanged.

### Requirement 7: Micro-Interactions & Transitions

**User Story:** As a user, I want subtle, tasteful motion, so that the app feels alive without being distracting or inaccessible.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled, THE Mobile_App SHALL apply tasteful micro-interactions (page transitions, card press feedback, list reveal) resolved through the A11y motion helper.
2. WHEN reduced motion is requested, THE Mobile_App SHALL collapse all non-essential animation to instant (`Duration.zero`).
3. THE micro-interactions SHALL never block or delay user input, and functional state changes SHALL remain available regardless of motion preference.
4. WHERE Experience_V2 is disabled, THE Mobile_App SHALL NOT apply Experience_V2 micro-interactions.

### Requirement 8: Branding

**User Story:** As a user, I want CLARA to look like a finished product, so that it is recognizable and trustworthy from the app icon onward.

#### Acceptance Criteria

1. THE Mobile_App SHALL set a human-readable display name consistent with CLARA branding on both platforms.
2. THE Mobile_App SHALL define an adaptive launcher icon and a themed splash that match the brand seed color and light/dark themes.
3. THE branding work SHALL be documented as generation/manifest steps (assets, sizes, manifest/plist keys) and SHALL NOT commit large binary assets to the repository.
4. WHERE a launcher-icon/splash generator package would normally be used, THE documentation SHALL note it as optional/manual so no new pubspec dependency is forced.
5. THE themed splash SHALL preserve the existing launch behavior (session hydration) and SHALL NOT introduce a fixed artificial delay.

### Requirement 9: Global Language Toggle & Accessibility

**User Story:** As a Vietnamese-first user who sometimes needs English, I want to switch languages and rely on assistive technology, so that the app works for me.

#### Acceptance Criteria

1. WHERE Experience_V2 is enabled, THE Mobile_App SHALL provide a global vi/en language toggle that applies app-wide and defaults to Vietnamese.
2. WHEN the user changes the language, THE Mobile_App SHALL persist the selection via `flutter_secure_storage` and SHALL restore it on subsequent launches.
3. THE Mobile_App SHALL provide screen-reader semantics for all interactive controls and primary content regions across Experience_V2 surfaces.
4. THE Mobile_App SHALL ensure interactive touch targets meet the platform minimum (≥48dp) and SHALL maintain a logical focus order.
5. THE Mobile_App SHALL respect dynamic text scaling and reduced motion, and SHALL convey status through text/semantics, not color alone, across Experience_V2 surfaces.
6. THE language preference and toggle interactions SHALL emit no PII to analytics.

### Requirement 10: Quality Gate

**User Story:** As an engineer, I want the modernization covered by tests and a clean analyzer, so that it ships safely and the off path is provably unchanged.

#### Acceptance Criteria

1. THE Mobile_App SHALL include a flags-off equivalence test asserting that, with `MOBILE_EXPERIENCE_V2_ENABLED` false, the reachable surfaces and navigation equal the pre-feature baseline (legacy `DashboardScreen` path).
2. THE Mobile_App SHALL include widget tests for the app shell, modern Home, onboarding, and theme/components covering loading, success, empty, and error states where applicable.
3. THE Mobile_App SHALL include tests asserting reduced motion collapses Experience_V2 animation to instant and that interactive controls expose semantics and meet ≥48dp targets.
4. THE Mobile_App SHALL include a test asserting Experience_V2 analytics events carry no PII.
5. THE test suite SHALL run under `flutter test` without requiring platform channels or live network access, and `flutter analyze` SHALL be clean.
6. THE Mobile_App SHALL retain its existing passing tests for analytics, accessibility, feature flags, and the session store.
