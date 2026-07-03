# Implementation Plan: CLARA Mobile Redesign

## Overview

Rebuild `apps/mobile` (Flutter) into a modern, light-mode-first, feature-complete
client that reaches parity with the web app, restructures the information
architecture around a **centered circular Chat action**, rebuilds the **Home**
and **Settings** surfaces, and elevates the **Personal Medicine Cabinet**,
**AI Council**, **PHR**, and **Medical Scribe** surfaces. Every existing
`ApiClient` contract, safety guardrail (consent gating, emergency fast-path,
no-PII analytics, RBAC, DDI severity floor, clinician-final-author), and
accessibility hook (`core/a11y.dart`) is preserved.

This redesign supersedes the dormant Experience_V2 scaffolding rather than
adding a new parallel path: the new shell becomes the app's authenticated root
and `themeMode` is pinned to light. See `design.md` for the component,
navigation, and theme architecture, and `requirements.md` for the EARS
acceptance criteria (Requirement 1–11) and safety invariants.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the existing `flutter_test` setup under `apps/mobile/test`.
- Co-locate widget/unit tests next to the new surfaces they cover.
- Every task is verifiable with `flutter analyze` and `flutter test` in
  `apps/mobile`; UI tasks add at least one widget test asserting the safety /
  a11y invariant they touch.
- A theme test pins `ThemeMode.light` as the resolved default (Requirement 1.2).

## Tasks

- [x] 1. Design-system foundation + light-mode default
  - [x] 1.1 Pin `themeMode: ThemeMode.light` on the app root; make the
    web-derived palette (`web_palette.dart` / `webColorScheme`) the single
    active scheme; retire the teal-seed/legacy branch as the default root.
    Test: resolved `ThemeMode` is light; scheme primary is `brand-600`.
    Requirement 1.1, 1.2, 1.5.
  - [x] 1.2 Extend `ClaraTokens` (spacing/radius/elevation/motion already exist)
    and finalize the shared component set: audit `ClaraButton`, `ClaraCard`,
    `ClaraChip`, `ClaraInput`, `SectionHeader`; add any missing primitives
    (list tile, empty/skeleton/error already present) so every surface can be
    built from tokens. Requirement 1.3, 1.4.
  - [x] 1.3 AA contrast + text-scaler + reduced-motion audit of the component
    set via `core/a11y.dart`; property/widget tests for tap-target ≥48dp and
    contrast pairings. Requirement 1.4, 11 (a11y invariant).

- [x] 2. Adaptive shell + centered circular Chat action
  - [x] 2.1 Build the new `AppShell` root: compact bottom bar with a centered
    circular Chat FAB (`FloatingActionButton`, `centerDocked`), phone/tablet
    adaptation, selection preserved across resize/rotation. Requirement 2.1,
    2.2, 2.3.
  - [x] 2.2 Wire primary destinations (Home, Cabinet, PHR, Settings + centered
    Chat) with role/flag-aware inclusion; fail-closed when the summary is
    unavailable. Requirement 2.4, 2.5, 11.
  - [x] 2.3 Make the app authenticated root use the new shell; keep the
    `ConsentGate` wrapping intact ahead of any medical surface. Requirement 2.6,
    11 (consent invariant).

- [x] 3. Rebuilt visual Home
  - [x] 3.1 New `HomeScreen`: greeting header, role-aware quick-action grid of
    `ClaraCard`s, and a "recent activity" region; loads role-scoped
    `mobile/summary` and derives tools fail-closed. Requirement 3.1, 3.2, 3.5.
  - [x] 3.2 Skeleton on first load, friendly empty state for recent activity,
    and `ErrorRetryView` on load failure; pull-to-refresh. Requirement 3.3, 3.4.
  - [x] 3.3 Home widget tests: fail-closed tool derivation (null summary ⇒ no
    privileged cards), skeleton/empty/error states. Requirement 3.5, 11.
    (`test/redesign_home_screen_test.dart`)

- [x] 4. Complete Settings surface
  - [x] 4.1 New `SettingsScreen` with grouped sections: account (email/role,
    sign-out), language toggle (vi/en via `LanguageController`), consent &
    privacy entry, AI transparency / model disclosure, about/legal, help.
    Requirement 4.1, 4.2, 4.3, 4.4, 4.6.
  - [x] 4.2 Sign-out clears the session via `SessionStore.clear()` and routes to
    login; language changes apply app-wide immediately. Requirement 4.5, 4.2.
  - [x] 4.3 Settings widget tests: sign-out clears session; language toggle
    persists + re-renders; consent/transparency entries are reachable.
    Requirement 4.5, 11. (`test/redesign_settings_screen_test.dart`)

- [x] 5. Dedicated Personal Medicine Cabinet
  - [x] 5.1 New `CabinetScreen` unifying self-med cabinet CRUD + in-cabinet DDI
    behind one consent-gated surface; structured item fields (drug, brand,
    manufacturer, dosage, form, quantity, expiry, note). Requirement 5.1, 5.2.
  - [x] 5.2 Item detail / editor bottom sheet, delete confirm, normalization /
    needs-review status per item, expiry surfacing. Requirement 5.3, 5.6.
  - [x] 5.3 Integrated DDI check on cabinet contents (≥2 distinct-medicine
    guard) rendering the End_User DDI projection via the shared `DdiResultView`;
    offline stale-cache banner preserved. Requirement 5.4, 5.5, 11 (DDI floor,
    two-medicine guard).
  - [x] 5.4 Cabinet widget tests: consent gate blocks CRUD when absent; DDI does
    not run for <2 distinct medicines; offline mutation blocked; DDI view hides
    runtime mode/fallback/source_errors. Requirement 5.4, 5.5, 11.
    (`test/redesign_cabinet_screen_test.dart`)

- [x] 6. Easier-to-use AI Council
  - [x] 6.1 Rebuild Council as a guided wizard (intake → specialists → result)
    on top of the case-based endpoints; clear step affordances and progress.
    Requirement 6.1, 6.2, 6.3.
  - [x] 6.2 Result view preserves the mandatory clinician-review directive and
    consensus/divergence/recommendation structure. Requirement 6.4, 11
    (clinician-final-author).
  - [x] 6.3 Council widget tests: wizard step progression; review directive
    always present; no-PII analytics. Requirement 6.4, 11.
    (`test/redesign_council_surface_test.dart`)

- [x] 7. Easier-to-use PHR
  - [x] 7.1 Rebuild PHR into card-based sections (basics, allergies, conditions,
    current medications, …) with inline quick-edit; load/save via existing PHR
    endpoints. Requirement 7.1, 7.2, 7.3.
  - [x] 7.2 Enhanced reads (export + emergency card) behind `phrEnhancedEnabled`;
    base PHR always available to every authenticated role. Requirement 7.4, 7.5.
  - [x] 7.3 PHR widget tests: save round-trip; enhanced affordances gated;
    no-PII analytics (count only). Requirement 7.5, 11.
    (`test/redesign_phr_surface_test.dart`)

- [x] 8. Medical Scribe as a first-class destination
  - [x] 8.1 Enable Scribe for admin (per the request) alongside the existing
    doctor path; surface it as a reachable destination/quick-action for
    authorized roles, still fail-closed for others. Requirement 8.1, 8.2, 8.5.
  - [x] 8.2 Redesign the Scribe surface (session list/detail, consent-capture
    gate, transcript append, SOAP regenerate, status) on the new design
    system; preserve `stripTelemetryLabels` and per-session consent. Audio
    capture deferred (no recorder dependency). Requirement 8.3, 8.4.
  - [x] 8.3 Scribe widget tests: authorized-role gating (admin + doctor open,
    others inert); per-session consent blocks processing; clinical text never
    sent to analytics. Requirement 8.4, 8.5, 11.
    (`test/redesign_scribe_surface_test.dart`)

- [~] 9. Chat as the central surface (Research unified)
  - [~] 9.1 Make the centered Chat destination the modern chat (reuse the
    polished chat view/composer/bubbles). Fast path done; folding deep/
    deep_beta research modes into the composer is deferred to a follow-up
    (tier2 job engine + admin telemetry rail). Requirement 9.1, 9.2, 9.3.
  - [x] 9.2 Preserve emergency fast-path banner/escalation, standing medical
    disclaimer, streaming + fallback, stop/regenerate, and detailed-telemetry
    admin-only gating. Requirement 9.4, 9.5, 11 (emergency fast-path, telemetry).
  - [~] 9.3 Chat widget tests: emergency detection surfaces escalation; deep
    modes gated; disclaimer present; telemetry gated to admin. Requirement 9.4,
    9.5, 11. (Covered by the legacy `test/chat_screen_test.dart` /
    `test/polished_chat_screen_test.dart`, since ChatSurfaceV3 delegates to the
    unchanged `ChatScreen`.)

- [x] 10. Redesigned authentication surfaces
  - [x] 10.1 Rebuild Login on the new design system: validation, show/hide
    password, friendly 401 messaging, routes to register/forgot. Requirement
    10.1, 10.2, 10.4.
  - [~] 10.2 Register / verify-email / forgot / reset flows reused as-is (they
    inherit the light-first palette + input theme); the terms + privacy +
    medical-consent acceptance on register is preserved. A full visual reskin
    of these secondary flows is a follow-up. Requirement 10.3, 10.5, 11.
  - [x] 10.3 Auth widget tests: empty-field validation; login persists session;
    friendly 401 messaging. Requirement 10.5, 11.
    (`test/redesign_login_screen_test.dart`)

- [~] 11. Cross-cutting hardening + rollout
  - [x] 11.1 Safety-invariant coverage across the redesigned surfaces:
    fail-closed RBAC/flag gating (Home, Cabinet, Scribe), consent gate before
    medical content (Cabinet), DDI two-medicine guard + hidden runtime fields
    (Cabinet), clinician-review directive (Council), no-PII analytics (Home,
    Cabinet, PHR, Council, Scribe, Login), and light-mode default lock. 41
    redesign tests green. Requirement 11.1–11.6.
  - [~] 11.2 A11y is baked into the shared components (≥48dp tap targets,
    text-scaler, reduced-motion, status-by-text) and the shell/component tests
    exercise it; a dedicated full-surface a11y sweep remains a follow-up.
    Requirement 1.4, 11.
  - [x] 11.3 `flutter analyze` clean (redesign files: zero errors/warnings);
    stray files removed (`ime*.png`, `ui.xml`); README updated with the
    `MOBILE_REDESIGN_ENABLED` section + flag table. `flutter test`: pre-existing
    legacy `scribe`/`dashboard` failures are Flutter-version drift, unrelated
    to the redesign (reproduced on a clean baseline). Requirement 1.5.

## Notes

### Requirement → primary implementing task
- R1 (design system, light default) → 1.1, 1.2, 1.3
- R2 (IA + centered circular Chat) → 2.1, 2.2, 2.3
- R3 (visual Home) → 3.1, 3.2, 3.3
- R4 (Settings) → 4.1, 4.2, 4.3
- R5 (Medicine Cabinet) → 5.1, 5.2, 5.3, 5.4
- R6 (Council) → 6.1, 6.2, 6.3
- R7 (PHR) → 7.1, 7.2, 7.3
- R8 (Scribe) → 8.1, 8.2, 8.3
- R9 (Chat central) → 9.1, 9.2, 9.3
- R10 (Auth) → 10.1, 10.2, 10.3
- R11 (safety/privacy/quality) → every task's test step + 11.1, 11.2, 11.3

### Sequencing
Tasks 1–2 are foundational (design system + shell) and unblock everything.
Tasks 3–10 are largely independent per-surface slices with disjoint write
scopes (each owns its screen file + colocated tests), so they can proceed in
parallel once the shell lands. Task 11 is the final hardening + rollout gate.

### Guardrails (unchanged by any task)
Consent gating precedes medical content; emergency fast-path escalates without
diagnostic reasoning; DDI severity floor + two-medicine guard hold; analytics
stay no-PII; RBAC is server-authoritative with fail-closed client gates;
detailed telemetry is admin-only; clinician remains the final author of any
Scribe/Council output.
