# Requirements — CLARA Mobile Unified (the all-new mobile app)

## Introduction

CLARA's Flutter app has accumulated **three parallel experience layers** — legacy
`screens/*` (the default authenticated root), Experience_V2 (`app_shell.dart`), and
the largely-built Experience_V3 redesign (`experience/redesign/*`) — selected by
compile-time flags that **all default OFF**, so a vanilla build still boots the
legacy Dashboard. The V3 redesign is the best baseline but ships dark, is a
**facade over legacy screens** (Home/Chat/Council route back into `screens/*`),
carries dead code (`CouncilSurfaceV3` is test-only), runs two color systems
(teal seed vs the web Fluent indigo palette), and is **missing the core consumer
surfaces the web now leads with**: Today, LifeMap, Visits, Family Circle, a
unified Medicines hub, standalone Evidence, and a first-run onboarding gate.

This feature delivers **one unified, modern, default-on CLARA mobile app** that
matches the current web product definition and IA, collapses the three layers
into a single experience, retires dead/duplicate code, and closes the
consumer-surface gaps — **without weakening any safety, consent, telemetry, or
accessibility invariant**.

### Product framing (must match web)
- CLARA is a Vietnamese, safety-first clinical **assistant, not a replacement for
  a doctor**. Safety guardrails are invariants.
- Consumer primary navigation mirrors web §6.1: **Today · LifeMap · (Ask CLARA) ·
  Medicines · Profile**. Chat is an input/explanation surface, not the IA root.
  Research is under "Explore evidence", not primary. Family Circle and Visits are
  reachable from Today/Profile, not primary tabs.

### Compatibility & rollout
- The unified experience becomes the **default** once this feature is complete.
  During build-out it lives behind `MOBILE_UNIFIED_ENABLED` (default OFF) so each
  phase ships dark and green; the final phase flips the default and removes the
  dead layers.
- All server calls stay on the existing `/api/v1/*` contract via `ApiClient`.
  No server behavior changes are required except the already-specced mobile
  feature-flag expansion (kept additive/flagged).

## Requirements

### Requirement 1: Single unified experience (collapse the 3 layers)
**User story:** As a user, I want one coherent app, so that behavior and visuals
never depend on which hidden build layer happens to load.

#### Acceptance Criteria
1. THE app SHALL boot into ONE experience root for authenticated users, replacing
   the 3-way `app.dart` branch (legacy Dashboard / V2 AppShell / V3 RedesignRoot).
2. WHEN `MOBILE_UNIFIED_ENABLED` is ON, THE app SHALL use the unified root and
   SHALL NOT mount the legacy `DashboardScreen` or `AppShell` as the root.
3. WHEN the feature is finalized, THE unified root SHALL be the default (flag ON
   by default) and the superseded `experience/app_shell.dart`, legacy
   `DashboardScreen` root wiring, and dead `CouncilSurfaceV3` (if still unwired)
   SHALL be removed or absorbed.
4. THE app SHALL use exactly ONE color system — the web-matching Fluent indigo
   palette (`web_palette.dart`) — for the unified experience; the teal seed path
   SHALL NOT be used by the unified root.
5. WHERE a legacy screen already implements correct, tested behavior (e.g. Chat
   streaming, Scribe, DDI), THE unified surface MAY reuse it, but the entry point,
   navigation, and chrome SHALL be the unified shell (no legacy shell/nav).

### Requirement 2: Product-aligned navigation & IA
**User story:** As a consumer, I want the mobile IA to match the product, so that
Today, LifeMap, Medicines and my Profile are one tap away.

#### Acceptance Criteria
1. THE unified shell SHALL present consumer primary navigation as **Today,
   LifeMap, a center Ask-CLARA action, Medicines, Profile** on phones (bottom),
   and an equivalent rail on tablets (≥600dp).
2. THE shell SHALL be role-aware: professional roles (doctor/admin/researcher)
   SHALL additionally reach their surfaces (Dashboard, Scribe, Council, Research,
   Admin reads) via the Profile/More area or role-added destinations, gated by the
   mobile summary `feature_flags` + role.
3. Chat SHALL be reachable from the center action from every primary tab; it SHALL
   NOT occupy a primary tab slot as the app's conceptual home.
4. Secondary consumer surfaces (Visits, Family Circle, Connected Health, Consent
   Center, Evidence, Settings, Guide) SHALL be reachable from Profile/More with
   consumer-friendly Vietnamese labels.
5. THE active-destination indication SHALL use ONE token-driven style across
   bottom nav and rail (no competing color systems).

### Requirement 3: Today surface (new)
**User story:** As a consumer, I want a Today view, so that I see only the care
tasks I have accepted and can act on them.

#### Acceptance Criteria
1. THE Today surface SHALL read `GET /api/v1/lifemap/today` and render accepted
   tasks, open episodes count, and pending-confirmation count.
2. THE surface SHALL let the user complete an accepted task via
   `POST /api/v1/lifemap/tasks/{id}/complete` with a generated `Idempotency-Key`.
3. WHEN there are no accepted tasks, THE surface SHALL show an empty state with a
   primary action to open LifeMap — it SHALL NOT fabricate tasks.
4. WHEN the profile has no health profile (409), THE surface SHALL route the user
   into onboarding/first-run rather than showing an error dead-end.
5. THE surface SHALL show loading, empty, error-retry, and offline states using
   the shared state widgets.

### Requirement 4: LifeMap surface (new)
**User story:** As a consumer, I want to organize what I track into small
journeys, so that CLARA supports me over time without diagnosing me.

#### Acceptance Criteria
1. THE LifeMap surface SHALL list open episodes (`GET /lifemap/today`) and let the
   user create an episode (`POST /lifemap/episodes`) and add + accept a task
   (`POST /lifemap/episodes/{id}/tasks` then `.../tasks/{id}/accept`), each with an
   `Idempotency-Key`.
2. Priority SHALL be one of routine/soon/urgent, rendered with the status token
   badges (no raw palette).
3. THE surface SHALL make clear (copy) that this is a personal plan, not a
   diagnosis.
4. Created/accepted items SHALL appear on Today after refresh.
5. WHERE the next-best-question endpoint is enabled
   (`GET /episodes/{id}/next-question`, 404 when off), THE surface MAY surface at
   most one question; when off it SHALL simply omit it.

### Requirement 5: Unified Medicines hub
**User story:** As a consumer, I want one Medicines place, so that my list,
cabinet, and interaction checks aren't three confusing screens.

#### Acceptance Criteria
1. THE Medicines surface SHALL be a single hub with tabbed sections mirroring web:
   **Danh sách** (confirmed medication courses), **Tủ thuốc** (cabinet + OCR), and
   **An toàn** (interaction analysis).
2. THE hub SHALL reuse the existing, tested cabinet CRUD, OCR
   (`scanCareguardCabinetFile` → `importCareguardDetections`), and DDI
   (`analyzeCareguard`) flows.
3. THE list section SHALL read/write medication courses
   (`GET/POST /api/v1/medication-courses`, POST needs `Idempotency-Key`, 409 when
   no profile).
4. THE consent gate, medical disclaimers, and low-confidence manual-confirm
   behavior SHALL be preserved exactly.
5. THE legacy standalone cabinet/careguard/selfmed screens SHALL NOT be primary
   destinations; the hub SHALL be the single medicines entry.

### Requirement 6: Visits & Family Circle (new, consumer secondary)
**User story:** As a consumer, I want to prepare for a visit and share minimally
with a caregiver, so that CLARA helps beyond a single chat.

#### Acceptance Criteria
1. THE Visits surface SHALL list and create visits (`GET/POST /api/v1/visits`),
   add concerns/intake answers, and view/approve a Visit Pack; mutations requiring
   `Idempotency-Key` (e.g. plan confirm) SHALL pass one.
2. THE Family surface SHALL list relationships, notifications, access grants, and
   the access log, invite a member (`POST /family/invitations`) and accept via the
   `X-Family-Invitation-Token` header, and revoke a grant.
3. Both surfaces SHALL enforce consent/RBAC as the server dictates and SHALL never
   surface PHI beyond what the grant/consent allows.
4. Both surfaces SHALL be reachable from Profile/More, not primary tabs.
5. Both SHALL show loading/empty/error/offline states via shared widgets.

### Requirement 7: First-run onboarding (parity with web `/welcome`)
**User story:** As a new user, I want a first-run setup, so that I create a health
profile and personalization choice before hitting a 409 dead-end.

#### Acceptance Criteria
1. THE unified root SHALL include an onboarding gate for authenticated users whose
   profile needs onboarding (`GET /api/v1/phr/onboarding`, `needs_onboarding`).
2. THE onboarding SHALL let the user save basics and complete or skip
   (`PATCH /api/v1/phr/onboarding` with action save/complete/skip), all fields
   optional, with a personalization-consent toggle.
3. WHEN onboarding is complete or skipped, THE app SHALL route to the role home
   (Today for consumers) and SHALL NOT show onboarding again.
4. WHEN the onboarding endpoint is unavailable, THE gate SHALL fail open (app
   remains usable).
5. THE onboarding SHALL apply to all roles, matching the corrected web behavior.

### Requirement 8: Design system unification & polish
**User story:** As a user, I want a modern, consistent look, so that the app feels
like one polished product.

#### Acceptance Criteria
1. THE unified experience SHALL render on `webColorScheme` + `ClaraStatusColors`
   with the diacritic-friendly typography scale; no teal-seed theme.
2. Clinical content SHALL remain opaque and meet WCAG AA contrast; any glass/blur
   chrome SHALL stay chrome-only and degrade to opaque on reduced-transparency or
   low-end devices.
3. Shared components (button, card, chip, input, section header, empty/skeleton/
   error/offline states) SHALL be used consistently; surfaces SHALL NOT hardcode
   raw palette values.
4. Motion SHALL honor reduced-motion; tap targets SHALL meet the a11y minimum.
5. Light and dark SHALL both resolve correctly from the theme controller.

### Requirement 9: Safety, consent, telemetry, and offline invariants (locked)
**User story:** As a stakeholder, I want the mobile guardrails preserved, so that
the redesign never becomes a softer path around safety.

#### Acceptance Criteria
1. THE emergency fast-path, standing medical disclaimer, End_User-safe answer
   projection, and model/AI-transparency disclosures SHALL be preserved on every
   surface that shows AI output.
2. Versioned medical consent SHALL gate medical content; granular consent + DSAR
   surfaces SHALL remain reachable and functional.
3. Analytics SHALL remain no-PII, suppressed until consent, and pseudonymous.
4. Network mutations SHALL be guarded when offline, with clear offline banners and
   error-retry; auth refresh/401-retry SHALL be preserved.
5. All new mutations requiring idempotency SHALL send a client-generated
   `Idempotency-Key`.

### Requirement 10: Quality gates
**User story:** As a maintainer, I want the app to stay green and analyzable.

#### Acceptance Criteria
1. `flutter analyze` SHALL report no new errors for changed files.
2. `flutter test` SHALL pass for all new/updated suites; new surfaces SHALL have
   widget tests covering render, empty, and error states, and safety gates.
3. Flag-off (`MOBILE_UNIFIED_ENABLED=false`) SHALL preserve the prior baseline
   until the finalization phase intentionally flips the default.
4. Dead code removed in finalization SHALL have no remaining references.
5. Tests SHALL assert the consumer primary-nav order and that Chat is not a
   primary conceptual home.
