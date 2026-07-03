# Requirements Document

Clara Mobile — Redesign (Experience_V3).

## Introduction

This feature is a **ground-up redesign of the CLARA_Mobile Flutter client**
(`apps/mobile`). The current mobile app is a functional-but-uneven client: a
modern "Experience_V2" scaffold (Material 3 `ClaraTheme`, adaptive `AppShell`,
a small `ClaraButton/Card/Chip/Input` component library, design tokens, and a
web-matching palette) exists but ships **dark behind compile-time flags**
(`MOBILE_EXPERIENCE_V2_ENABLED`, `MOBILE_UX_POLISH_ENABLED`, both default OFF),
so the default runtime is the legacy teal-seed `DashboardScreen`. Even with the
V2 flag on, the surfaces are split across two visual tiers: **Chat and the
Consent Center** are polished against explicit UX/a11y requirements, while
**Home, Settings, PHR, Council, Research, the two medicine cabinets, Scribe, and
Auth** are raw Material with hardcoded colors and prototype-grade layouts. The
web app (`apps/web`) is the mature product and is treated as the **feature and
quality reference** ("gold standard") for parity.

The redesign delivers a cohesive, modern, **light-mode-first** mobile experience
that reaches feature parity with the web app's primary end-user surfaces, and it
**restructures the app's information architecture** — including a new visual
navigation with a **centered circular Chat action** in the bottom navigation
bar. It rebuilds the **Home** (dashboard) surface into a visual, role-aware
landing, builds a **complete Settings** surface (theme, language, account,
privacy, about, and app preferences — replacing today's near-empty placeholder),
splits **Personal Medicine Cabinet ("Tủ thuốc cá nhân")** into its own richly
featured destination, makes **AI Council ("Hội chẩn AI")** and **PHR** materially
easier to use, and **enables Medical Scribe** as a first-class destination.

### Redesign posture (differs from prior additive specs)

Unlike prior mobile specs (`clara-mobile-experience`, `clara-mobile-feature-parity`,
`clara-mobile-ux-polish`) which were strictly additive and default-OFF, this
redesign **replaces** the default mobile experience. The new experience becomes
the app's default. Consequences and constraints:

- **No backend contract changes.** Every surface reuses the existing
  `ApiClient` methods and CLARA_API `/api/v1/*` endpoints exactly as they are
  today. This is a **client-only** redesign.
- **All safety guardrails are preserved as invariants** (see the Safety
  Invariants section): consent gating before medical content, per-session
  Scribe consent, no-PII analytics, RBAC/role-scoped feature gates from
  `mobile/summary`, the DDI two-medicine guard and severity floor, the emergency
  fast-path, and the mandatory clinician-review / not-a-doctor disclaimers.
- **Feature-flag gates are retained** as capability gates (they decide which
  destinations are reachable for a role/build), even though the *visual*
  redesign itself is the new default. A capability whose flag is off must degrade
  to a calm, reachable "not available" state, never a crash or a dead tab.
- **Reference target.** Where a decision is ambiguous, the web app's behavior,
  copy, and information architecture are the tie-breaker.

CLARA remains a **Vietnamese-first clinical assistant that explicitly does not
replace a doctor**. All primary copy is Vietnamese-first (English available via
the language toggle). Nothing here changes CLARA's positioning as decision-support
over self-declared data — not a medical device, not an EMR/EHR, not a prescriber.

### Goals

- A single, cohesive, modern, light-mode-first design system applied uniformly
  across **every** mobile surface (no more two-tier polish split).
- Feature parity with the web app's end-user surfaces: Chat, Home/Dashboard,
  Personal Medicine Cabinet, CareGuard/DDI, AI Council, Medical Scribe, PHR,
  Research (unified into Chat modes), Settings, and account/consent.
- A restructured information architecture with a visual bottom navigation whose
  **centered circular button opens Chat**.
- Easier task flows for the surfaces the user called out as hard to use (Council,
  PHR) and a dedicated, feature-rich Personal Medicine Cabinet.
- Preserve every safety guardrail and the no-PII analytics discipline.

### Non-Goals

- No changes to CLARA_API, CLARA_ML, or any server contract.
- No autonomous diagnosis or prescribing (unchanged positioning).
- No new third-party backend integrations; audio capture remains dependent on a
  host-injected provider unless a recorder dependency is explicitly added in the
  design phase.
- Not a re-architecture of state management or networking beyond what the UI
  redesign requires (the app keeps `ChangeNotifier` + `ApiClient` unless the
  design phase justifies otherwise).

## Glossary

- **Experience_V3 / the redesign**: the new default mobile UI delivered by this
  spec, superseding the flag-gated Experience_V2 as the default surface.
- **Design system**: the shared token set (`ClaraTokens`), color palette
  (`WebPalette`/`ClaraTheme`), typography (`ClaraTypography`), and component
  library (`ClaraButton`, `ClaraCard`, `ClaraChip`, `ClaraInput`, `SectionHeader`,
  and new components introduced here) that all surfaces consume.
- **Shell**: the adaptive navigation scaffold (`AppShell`) hosting primary
  destinations — a bottom navigation bar on compact widths and a navigation rail
  on medium/expanded widths.
- **Centered Chat action**: the circular, visually distinct navigation control at
  the horizontal center of the compact bottom navigation that opens the Chat
  surface.
- **Primary destination**: a top-level surface reachable directly from the shell
  navigation (e.g. Home, Medicine Cabinet, Chat, Council/Clinical, Settings).
- **Secondary surface**: a surface reached by navigating from a primary
  destination (e.g. a cabinet item editor, a Council case, a Research deep run).
- **Role-scoped summary**: the `feature_flags` + role payload from
  `GET /api/v1/mobile/summary` used to resolve capability gates
  (`MobileFeatureFlagResolver`).
- **Capability gate**: a feature flag (server role-scoped and/or build-time
  `--dart-define`) that determines whether a capability/destination is available.
- **PHR**: Personal Health Record — the self-reported record surface.
- **DDI**: Drug-Drug Interaction analysis (CareGuard).
- **Personal Medicine Cabinet ("Tủ thuốc cá nhân")**: the per-user medicine list
  and its management surface, elevated here to a dedicated primary destination
  with reminders, expiry tracking, and integrated safety checks.
- **Council**: the multi-specialist AI case-consultation surface.
- **Scribe**: the ambient clinical-documentation (SOAP note) surface.
- **No-PII analytics**: the existing discipline that mobile analytics events
  carry only counts/booleans/enums and never names, emails, free-text, or drug
  lists.
- **Light-mode-first**: the app defaults to the light theme on first launch,
  regardless of OS setting; the user may opt into dark or system in Settings.

## Safety Invariants (regression-locked; every requirement inherits these)

- **INV-1 Consent gating**: medical-content surfaces remain behind the existing
  consent gate; the redesign never renders gated medical content before consent
  is satisfied.
- **INV-2 Scribe per-session consent**: Scribe never processes audio/transcript
  for a session before that session's consent is captured; revoke remains
  available.
- **INV-3 No-PII analytics**: every analytics event emitted by any redesigned
  surface carries only non-PII fields; clinical text is passed through the
  existing sanitizer before any display that could reach telemetry, and never
  sent to analytics.
- **INV-4 RBAC / capability gates**: privileged destinations are derived only
  from a successfully loaded role-scoped summary and fail **closed** (no summary
  ⇒ no privileged destinations); Scribe additionally requires the doctor role.
- **INV-5 DDI guards**: the two-distinct-medicine guard and the severity-floor /
  never-fabricate-all-clear behavior of the DDI user view are preserved; the
  End_User DDI projection continues to hide runtime `mode`/`fallback`/`source_errors`.
- **INV-6 Emergency fast-path**: acute-symptom detection continues to surface
  urgent-care escalation without diagnostic reasoning.
- **INV-7 Not-a-doctor / clinician-review**: the standing medical disclaimer and
  the mandatory clinician-review directive on Council/Scribe results are always
  present.
- **INV-8 No backend contract change**: no requirement in this spec alters any
  CLARA_API request/response contract.

## Requirements

### Requirement 1: Unified, modern, light-mode-first design system

**User Story:** As a mobile user, I want a single cohesive, modern visual design
across every screen, so that the app feels polished and consistent rather than a
patchwork of prototype screens.

#### Acceptance Criteria

1. THE Mobile_App SHALL apply one shared design system (tokens, palette,
   typography, components) to every primary destination and secondary surface,
   with no screen rendering raw unthemed Material defaults or hardcoded ad-hoc
   colors for semantic state.
2. THE Mobile_App SHALL default to the light theme on first launch regardless of
   the OS brightness setting.
3. THE Mobile_App SHALL let the user choose light, dark, or system theme from
   Settings, and SHALL persist that choice across launches.
4. WHERE the user has not chosen a theme, THE Mobile_App SHALL resolve to light.
5. THE design system SHALL express semantic status (success, warning, danger,
   info/neutral) through named palette roles rather than hardcoded color
   literals at call sites.
6. THE Mobile_App SHALL preserve the existing accessibility hooks (text scaling,
   reduced motion, ≥48dp tap targets, semantics/labels) on every redesigned
   surface.
7. THE Mobile_App SHALL meet WCAG AA contrast for text and essential UI in both
   light and dark themes. (Full validation requires manual assistive-technology
   testing; automated checks cover token/pairing contrast.)
8. THE redesigned experience SHALL be the app's default surface after login
   (superseding the legacy `DashboardScreen` default), while preserving all
   safety invariants.

### Requirement 2: Restructured information architecture with a centered circular Chat action

**User Story:** As a mobile user, I want clear, visual navigation with quick
access to Chat, so that I can move between the app's main areas without
confusion.

#### Acceptance Criteria

1. THE Shell SHALL present a restructured set of primary destinations that
   reflects the redesigned information architecture (not the legacy four-tab set).
2. WHERE the viewport is compact (phone width), THE Shell SHALL render a bottom
   navigation with a **centered, circular, visually distinct Chat action**.
3. WHEN the user activates the centered Chat action, THE Shell SHALL open the
   Chat surface.
4. WHERE the viewport is medium or expanded (tablet/large width), THE Shell SHALL
   render a navigation rail that includes a Chat destination, preserving access
   to Chat without requiring the compact circular control.
5. THE Shell SHALL preserve the selected destination across width and orientation
   changes.
6. THE Shell SHALL guarantee every navigation control a ≥48dp tap target and a
   single, correct accessibility announcement (no double-announce).
7. WHERE a destination's capability gate is off for the current role/build, THE
   Shell SHALL either omit that destination or present it in a calm,
   non-crashing "not available for your role" state, and SHALL never expose a
   privileged destination to an unauthorized role (INV-4).
8. THE Shell SHALL derive privileged destinations only from a successfully loaded
   role-scoped summary and fail closed when the summary is unavailable (INV-4).

### Requirement 3: Rebuilt visual Home

**User Story:** As a user, I want an informative, visual home screen, so that I
can see relevant tools and recent activity at a glance instead of a bare list.

#### Acceptance Criteria

1. THE Home_Surface SHALL present a role-aware landing with a personalized
   greeting, a visually organized set of tool entries, and a recent-activity
   region.
2. THE Home_Surface SHALL derive privileged tool entries only from a successfully
   loaded role-scoped summary and fail closed (no summary ⇒ only universally
   available entries such as PHR), per INV-4.
3. WHILE the first role-scoped summary is loading, THE Home_Surface SHALL show a
   skeleton/loading state rather than a blank region.
4. IF the summary fails to load, THEN THE Home_Surface SHALL show a Vietnamese-first,
   PII-free error with a retry affordance and SHALL show no privileged entries.
5. THE Home_Surface SHALL support pull-to-refresh that reloads the role-scoped
   summary.
6. THE Home_Surface SHALL visually distinguish available from unavailable tools
   and route each available tool to its destination.
7. THE Home_Surface SHALL surface entries for the redesigned primary areas,
   including the Personal Medicine Cabinet, and SHALL respect each area's
   capability gate.
8. THE Home_Surface SHALL emit only no-PII analytics (e.g. a coarse screen-view),
   per INV-3.

### Requirement 4: Complete Settings surface

**User Story:** As a user, I want a full settings screen with real options, so
that I can control the app's appearance, language, account, and privacy instead
of seeing a near-empty placeholder.

#### Acceptance Criteria

1. THE Settings_Surface SHALL replace the current placeholder with a structured,
   sectioned settings experience.
2. THE Settings_Surface SHALL provide a theme control (light/dark/system) that
   applies immediately and persists (Requirement 1.3).
3. THE Settings_Surface SHALL provide the language toggle (Vietnamese/English)
   that applies app-wide and persists.
4. THE Settings_Surface SHALL present an account section showing the signed-in
   identity (role and email as already held by the session) and a sign-out
   action that clears the session.
5. THE Settings_Surface SHALL provide entry points to privacy/consent management
   (Consent Center and, where its gate is on, data-subject requests), gated by
   their existing capability flags and failing closed when off.
6. THE Settings_Surface SHALL present an "about" section (app version/build and
   the model/AI-transparency disclosure) using the existing disclosure sources,
   respecting their capability gates.
7. THE Settings_Surface SHALL preserve the not-a-doctor positioning and link to
   the relevant legal/consent information available to the client.
8. THE Settings_Surface SHALL emit only no-PII analytics and SHALL not display
   secret values (tokens) anywhere.

### Requirement 5: Dedicated, feature-rich Personal Medicine Cabinet

**User Story:** As a user, I want a dedicated, well-crafted personal medicine
cabinet, so that I can manage my medicines with reminders, expiry tracking, and
built-in safety checks.

#### Acceptance Criteria

1. THE Cabinet_Surface SHALL be a dedicated primary destination distinct from the
   ad-hoc DDI checker, presenting the user's medicine list with full create,
   read, update, and delete operations scoped to their own cabinet, reusing the
   existing cabinet endpoints.
2. THE Cabinet_Surface SHALL remain behind the existing medical consent gate
   (INV-1) and SHALL support the existing structured item fields (drug name,
   brand, manufacturer, dosage, form, quantity, expiry, note) as exposed by the
   API.
3. THE Cabinet_Surface SHALL surface each item's expiry status (e.g. expired /
   expiring soon / valid) computed from the item's expiry field, without
   inventing data the API does not provide.
4. THE Cabinet_Surface SHALL provide an integrated drug-interaction (DDI) check
   over the cabinet's contents, preserving the two-distinct-medicine guard and
   the End_User DDI projection (INV-5).
5. WHERE the device is offline, THE Cabinet_Surface SHALL block mutations with a
   clear offline state and SHALL, where the offline-cache capability is enabled,
   show the last-known DDI result labeled as stale (INV-5).
6. WHERE a medication-reminder capability is provided by this redesign, THE
   Cabinet_Surface SHALL let the user configure reminders per item using
   device-local scheduling only, SHALL require any new capability to be gated and
   default off, and SHALL NOT transmit reminder data to any new backend endpoint.
7. WHERE a reminder or any new client capability requires a new dependency or OS
   permission, THE design phase SHALL document it and THE capability SHALL degrade
   gracefully when the permission is denied.
8. THE Cabinet_Surface SHALL emit only no-PII analytics (counts/booleans; never
   drug names or lists), per INV-3.

### Requirement 6: Easier-to-use AI Council

**User Story:** As a clinician, I want the AI Council to be easy to use, so that I
can assemble a multi-specialty consultation without wrestling with a dense form.

#### Acceptance Criteria

1. THE Council_Surface SHALL present a guided, step-based flow (e.g. intake →
   specialist selection → result) rather than a single dense form.
2. THE Council_Surface SHALL reuse the existing case-based Council endpoints
   (create case, intake, run) and preserve case persistence where the API
   provides it.
3. THE Council_Surface SHALL clearly show progress through the steps and allow
   moving between steps without losing entered data within a session.
4. THE Council_Surface SHALL render the consensus, divergence, and final
   recommendation from the run envelope, and SHALL always display the mandatory
   clinician-review directive on every result (INV-7).
5. THE Council_Surface SHALL be gated by the existing Council capability
   (role-scoped) and fail closed when unavailable (INV-4).
6. THE Council_Surface SHALL emit only no-PII analytics, per INV-3.

### Requirement 7: Easier-to-use PHR

**User Story:** As a user, I want the PHR to be easy to read and edit, so that I
can keep my self-reported health record current without navigating a wall of
fields.

#### Acceptance Criteria

1. THE PHR_Surface SHALL present the self-reported record organized into
   scannable sections (e.g. basic info, allergies, conditions, medications) with
   a clear read view and a focused edit experience.
2. THE PHR_Surface SHALL load and persist the record via the existing PHR
   endpoints without changing their contract.
3. THE PHR_Surface SHALL be available to every authenticated role (it is not
   gated by a privileged capability), consistent with current behavior.
4. WHERE the enhanced-PHR capability is enabled, THE PHR_Surface SHALL expose the
   enhanced read affordances (e.g. export, emergency card) gated by that flag and
   failing closed when off.
5. THE PHR_Surface SHALL validate edits minimally (e.g. required/format where the
   API expects it) and SHALL surface save success and failure states clearly.
6. THE PHR_Surface SHALL emit only no-PII analytics (e.g. a total entry count),
   per INV-3.

### Requirement 8: Medical Scribe enabled as a first-class destination

**User Story:** As a doctor, I want Medical Scribe available and polished, so that
I can capture an encounter and generate a SOAP note from the mobile app.

#### Acceptance Criteria

1. THE Scribe_Surface SHALL be reachable as a first-class destination for the
   doctor role when its capability gate is on, and SHALL fail closed (inert,
   no calls) for unauthorized roles or when the gate is off (INV-4).
2. THE Scribe_Surface SHALL capture per-session consent before processing any
   audio or transcript, and SHALL support revoke, preserving INV-2.
3. THE Scribe_Surface SHALL support listing, creating, and opening sessions,
   appending transcript text, transcribing audio where a host audio provider is
   available, and regenerating the SOAP note, reusing the existing Scribe
   endpoints.
4. THE Scribe_Surface SHALL show session status (e.g. draft/ready/finalized/error)
   and SHALL pass clinical text through the existing sanitizer before any display
   path that could reach telemetry (INV-3).
5. WHERE audio capture requires a recorder capability not currently present, THE
   design phase SHALL document the dependency/permission and THE surface SHALL
   degrade gracefully (text-append still works) when audio is unavailable.
6. THE Scribe_Surface SHALL always display the not-a-doctor / clinician-review
   framing appropriate to generated notes (INV-7).
7. THE Scribe_Surface SHALL emit only no-PII analytics, per INV-3.

### Requirement 9: Chat as the central surface (Research unified)

**User Story:** As a user, I want one central Chat surface with fast and deep
answer modes, so that research and Q&A live in one place like the web app.

#### Acceptance Criteria

1. THE Chat_Surface SHALL be opened by the centered circular navigation action
   (Requirement 2.3) and SHALL be the app's primary conversational surface.
2. THE Chat_Surface SHALL support the existing answer modes — fast (synchronous)
   and deep/deep_beta (asynchronous job with streamed progress) — reusing the
   existing chat and research endpoints, with deep modes gated by their existing
   capability and degrading to fast-only when off.
3. THE Chat_Surface SHALL preserve the existing streaming/blocking behavior,
   stop/regenerate/copy actions, emergency-fast-path banner (INV-6), standing
   medical disclaimer (INV-7), and offline gating.
4. THE Chat_Surface SHALL render detailed research telemetry only for the admin
   role and SHALL sanitize otherwise (INV-3).
5. THE Chat_Surface SHALL adopt the unified design system consistently with all
   other surfaces (Requirement 1).
6. THE Chat_Surface SHALL emit only no-PII analytics, per INV-3.

### Requirement 10: Redesigned authentication surfaces

**User Story:** As a user, I want polished sign-in and account-lifecycle screens,
so that logging in and managing my account feels consistent with the rest of the
app.

#### Acceptance Criteria

1. THE Auth_Surfaces (login, register, verify email, forgot password, reset
   password) SHALL adopt the unified design system.
2. THE Auth_Surfaces SHALL reuse the existing auth endpoints without contract
   changes and SHALL persist the session via the existing session store.
3. THE Login_Surface SHALL provide a show/hide password affordance and clear,
   Vietnamese-first validation and error states (including a friendly message on
   invalid credentials).
4. THE Register_Surface SHALL preserve the existing required consents
   (terms/privacy/medical consent) before account creation.
5. THE Auth_Surfaces SHALL emit only no-PII analytics (e.g. viewed/succeeded
   without identifiers), per INV-3.
6. THE Auth_Surfaces SHALL never display secret values and SHALL handle
   session-expiry with the existing Vietnamese message.

### Requirement 11: Safety, privacy, and quality preserved end-to-end

**User Story:** As a safety stakeholder, I want the redesign to preserve every
guardrail and quality gate, so that a visual overhaul never weakens CLARA's
safety posture.

#### Acceptance Criteria

1. THE redesign SHALL preserve INV-1 through INV-8 on every surface it touches.
2. THE redesign SHALL make no change to any CLARA_API/ML contract (INV-8).
3. THE redesign SHALL keep every capability gate (server role-scoped and
   build-time) functioning as a fail-closed capability gate.
4. THE redesign SHALL pass the mobile analyzer/lints and the Flutter test suite,
   and SHALL add widget/unit tests for new components and for the fail-closed and
   no-PII behaviors it introduces.
5. THE redesign SHALL keep all primary copy Vietnamese-first with English
   available via the language toggle.
6. WHERE the redesign introduces a new dependency or OS permission, THE change
   SHALL be documented in the design and SHALL degrade gracefully when denied.
