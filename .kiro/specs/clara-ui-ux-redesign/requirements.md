# Requirements — CLARA UI/UX Redesign

## Introduction

CLARA's web app grew feature-by-feature. The result is a functional but visually
dated, inconsistent surface: overlapping medication pages, four hand-maintained
navigation renderers, per-page bespoke controls, drifting page widths, and a flat
single-blue palette with weak depth. New users land without a clear first step and
must self-navigate an information architecture built around internal service names
rather than user goals.

This redesign delivers a **modern, coherent, beginner-friendly** experience without
weakening any safety guardrail. It consolidates redundant surfaces, unifies the
navigation and layout system, standardizes on a single design-token + primitive
library, and makes the first-run and everyday paths obvious. It is a
**presentation and information-architecture** effort: no medical logic, RBAC,
consent, emergency, FIDES, or telemetry-PII behavior changes.

## Glossary

- **Surface** — a top-level user-facing page or feature area (e.g. Chat, LifeMap).
- **Primitive** — a shared, reusable UI component (`Button`, `Field`, `Badge`,
  `SurfaceCard`, etc.) under `apps/web/components/ui`.
- **Design token** — a CSS custom property in `globals.css` (`--brand-*`,
  `--surface-*`, `--text-*`, `--radius-*`, `--shadow-*`, type scale) that is the
  single source of truth for a visual value.
- **Shell** — the persistent app frame: sidebar (desktop), top command bar, mobile
  bottom nav, and the content canvas.
- **First-run** — the experience for a user whose health profile onboarding status
  is `pending`.
- **IA** — information architecture: the set of surfaces, their grouping, labels,
  and navigation order.

## Requirements

### Requirement 1: Unified, goal-oriented navigation

**User story:** As a user, I want a single clear navigation that is organized around
what I want to do, so that I am not confused by overlapping or internally-named
entries.

#### Acceptance criteria
1. THE navigation SHALL be defined once in a single source of truth and rendered by
   shared components; there SHALL NOT be four independently hand-maintained
   renderers with divergent active-state styling.
2. WHEN a consumer (role `normal`) views navigation, THE system SHALL present
   primary items grouped by user goal (e.g. Today, LifeMap, Medicines, Visits,
   Chat, Profile) and SHALL NOT surface researcher/clinician/admin-only areas.
3. THE navigation labels SHALL use user-facing language, not internal service names
   (e.g. no raw "tier2", "FIDES", "source-hub" in a consumer label).
4. THE active navigation item SHALL use one consistent visual treatment across
   desktop sidebar, mobile drawer, and mobile bottom nav.
5. WHERE a route is role-gated, an unauthorized user SHALL NOT see its nav entry and
   SHALL be redirected by the existing guard if they navigate to it directly
   (unchanged RBAC behavior).

### Requirement 2: Consolidated medication experience

**User story:** As a user, I want one place to manage my medicines and their safety,
so that I am not split across three overlapping pages.

#### Acceptance criteria
1. THE medication surfaces currently split across "Tủ thuốc" (`/selfmed`), "Thuốc
   của tôi" (`/medicines`), and "Kiểm tra tương tác" (`/careguard`) SHALL be
   presented under one coherent Medicines area with clear sub-sections, not three
   sibling top-level nav items with overlapping purpose.
2. WHEN the consolidation changes a route, THE system SHALL preserve the old route
   as a redirect so existing links and bookmarks do not break.
3. THE consolidation SHALL preserve every existing capability (cabinet, OCR scan,
   confirmed medication list, DrugBank DDI check, allergy-aware analysis) and every
   safety gate (consent, disclaimers, low-confidence manual confirm).
4. THE DrugBank/DDI "only conclude when the index is complete" invariant SHALL be
   preserved verbatim.

### Requirement 3: Consistent layout and content width

**User story:** As a user, I want every page to feel like part of the same product,
so that content does not jump width or alignment as I move between pages.

#### Acceptance criteria
1. All non-immersive pages SHALL share one consistent maximum content width and
   horizontal gutter; page-to-page navigation SHALL NOT change the content column
   width.
2. Immersive surfaces (Chat, Research, Council, Scribe) MAY use a full-bleed
   working area, but SHALL share consistent outer padding and header treatment.
3. Every standard page SHALL render its title/description through one shared page
   header component with a consistent type scale and spacing.
4. THE layout SHALL be responsive with defined behavior at mobile (<640px), tablet
   (640–1024px), and desktop (≥1024px) breakpoints, meeting a 44px minimum touch
   target on interactive controls.

### Requirement 4: Single design-token + primitive system

**User story:** As a user, I want a visually modern and internally consistent
interface, so that the product feels trustworthy and current.

#### Acceptance criteria
1. All colors, radii, shadows, and typography on redesigned surfaces SHALL derive
   from design tokens; no hardcoded hex color utilities SHALL be introduced (the
   existing token regression guard SHALL continue to pass).
2. Buttons, inputs, selects, textareas, badges, cards, empty/loading/error states,
   and modals SHALL be provided by the shared primitive library and reused rather
   than re-declared per page.
3. THE palette SHALL provide clear surface elevation and a modern brand identity
   with adequate depth (not flat white-on-white), in both light and dark themes.
4. All used foreground/background token pairs SHALL meet WCAG 2.1 AA contrast
   (normal text ≥ 4.5:1, large text/UI ≥ 3:1); the existing contrast property test
   SHALL continue to pass.
5. THE dead/duplicate visual layers (neutralized glass/glow/gradient CSS, unused
   `medical` palette, aliased `sky/teal/cyan`→blue traps, dead FontAwesome) SHALL be
   removed or reconciled so there is one coherent styling system.

### Requirement 5: Beginner-friendly first-run and empty states

**User story:** As a new user, I want an obvious first step and helpful guidance,
so that I am not dropped into an empty or blocked screen.

#### Acceptance criteria
1. WHEN a user's onboarding status is `pending`, THE system SHALL route them to a
   welcoming first-run flow for every role, not only `normal`.
2. THE first-run flow SHALL explain CLARA's value and scope, request only what the
   first useful experience needs, allow skipping optional steps, and never require
   a clinical answer (consistent with the LifeMap `LIFE-00x` requirements).
3. WHEN a data surface is empty, THE system SHALL show a friendly empty state with a
   clear primary action, not a blank area or a raw error.
4. WHEN a user completes or skips onboarding, THE system SHALL land them on a useful
   home (Today for consumers) and SHALL NOT return them to a blocked screen.
5. THE first-run and primary surfaces SHALL NOT surface internal telemetry labels or
   raw upstream errors to the End_User (existing clarity invariant).

### Requirement 6: Accessibility and keyboard support

**User story:** As a user relying on assistive technology or a keyboard, I want the
redesigned surfaces to remain fully operable.

#### Acceptance criteria
1. Every interactive control SHALL expose a visible focus indicator via the shared
   focus-ring tokens and SHALL remain visible under forced-colors mode (existing
   focus test SHALL continue to pass).
2. THE shell SHALL keep a skip link to `#main-content` as the first focusable
   element and a logical tab order.
3. Interactive custom controls (toggles, tabs, menus) SHALL carry correct ARIA
   roles/states.
4. Motion SHALL respect `prefers-reduced-motion`.

### Requirement 7: No regression of safety, behavior, or tests

**User story:** As the CLARA team, I want the redesign to be provably safe, so that
no guardrail or contract is weakened.

#### Acceptance criteria
1. RBAC role-gating, consent gating, the emergency fast-path, FIDES verification,
   no-PII telemetry, CSRF, the legal hard-guard, and End_User clarity SHALL be
   unchanged in behavior.
2. THE existing web test suite (Vitest + property tests) and the API/ML suites
   SHALL pass; new UI logic SHALL be covered by tests where it carries logic
   (navigation model, redirects, route consolidation).
3. WHERE a route is removed or moved, a redirect SHALL preserve deep links.
4. THE `next lint` and production build SHALL pass with no new errors.
