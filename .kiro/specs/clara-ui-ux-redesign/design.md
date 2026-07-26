# Design — CLARA UI/UX Redesign

## Overview

This is a presentation + IA redesign of `apps/web`. It standardizes the shell,
navigation, layout, and visual system on one design-token + primitive foundation,
consolidates redundant surfaces (medications; research/evidence), and makes
first-run and empty paths beginner-friendly. No backend contract, RBAC, consent,
emergency, FIDES, or telemetry-PII behavior changes.

The work is **incremental and reversible**: every phase keeps the app building and
green, old routes redirect rather than 404, and safety-locked tests
(contrast/focus/tokens/nav/chat-theme) remain the gate.

## Architecture

```
apps/web
├── app/                         # routes (unchanged set, minus consolidated dupes → redirects)
│   ├── layout.tsx               # fonts + theme init + AppShell
│   ├── welcome/                 # first-run onboarding (all roles)
│   ├── today · lifemap · visits · family · phr · chat · research · evidence
│   ├── medicines/               # CONSOLIDATED medicines hub (tabs: list · cabinet · safety)
│   ├── selfmed · careguard      # → redirect into /medicines sub-sections
│   └── admin/* · council · scribe · community · account/* · legal/*
├── components/
│   ├── app-shell.tsx            # shell frame (one width system, one gate)
│   ├── navigation/              # ONE nav model → shared renderers
│   │   ├── nav-model (from lib/navigation.config.ts)
│   │   ├── sidebar-nav · mobile-drawer · mobile-bottom-nav · app-topbar
│   └── ui/                      # PRIMITIVES: button, field, badge, surface, page-shell,
│                                #   tabs, modal, toggle, async-section, stat-card
├── lib/navigation.config.ts     # single IA source of truth (goal-oriented groups)
└── styles/globals.css           # design tokens (light/dark) + minimal component CSS
```

### Design principles
- **One source of truth per concern.** IA in `navigation.config.ts`; visual values
  in tokens; controls in `components/ui`. Renderers read from these, never fork.
- **Goal-oriented IA.** Groups reflect user intent (Care, Medicines, Explore,
  Clinical, Admin, Support), not internal service names.
- **Consolidate, don't delete.** Overlapping surfaces merge behind tabs; old routes
  redirect so links survive.
- **Safety is invariant.** Guardrail tests are the gate; no medical/consent/RBAC
  logic is touched.
- **Beginner-first.** Obvious first step, friendly empty states, plain language.

## Components and Interfaces

### 1. Design tokens (`styles/globals.css`)
- **Foundation:** tinted canvas with real elevation tiers (`--bg-elev-1/2/3`
  distinct), refined indigo-blue brand ramp, layered modern shadow scale
  (`--shadow-sm/soft/float/hero`), full radius scale, formal type scale
  (`--text-display/title/heading/body/caption`), Inter webfont.
- **Reconcile legacy:** remove/neutralize dead glass/glow/gradient rules, the unused
  `medical` palette, and the `sky/teal/cyan→blue` Tailwind aliases; FontAwesome
  already removed.
- **Constraint:** the `:root` and `html.dark` text/status token *values* consumed by
  `contrast.test.ts` keep AA; focus-ring tokens and the `.clara-chat-v2` canvas rule
  consumed by `focus-accessibility.test.ts` / `chat-shell-theme.test.ts` are
  preserved.

### 2. Primitive library (`components/ui`)
Existing: `Button` (variants/sizes/loading/link), `Field`/`Select`/`Textarea`,
`Badge`, `SurfaceCard`/`StatCard`/`EmptyState`/`InlineError`/`LoadingCards`,
`PageShell`, `AsyncSection`.
Add as needed: `Tabs` (for the Medicines hub and multi-section pages), `Modal`
(replace bespoke modals, e.g. community compose), `Toggle` (switch used in welcome +
consent). All token-driven, keyboard-accessible, reduced-motion aware.

### 3. Navigation model (`lib/navigation.config.ts`)
- Regroup into goal-oriented groups with consumer-friendly labels.
- Add a small `renderers` layer so sidebar / drawer / bottom-nav / topbar all consume
  `getGroupedNavItems(role)` and a shared `<NavItem>` with one active-state style.
- Keep `PUBLIC_ROUTES`, RBAC role arrays, `isActiveRoute`, `resolvePostLoginPath`,
  and `isAuthenticatedUtilityRoute` (tested contracts) intact; extend, don't rewrite.

### 4. Shell (`components/app-shell.tsx`)
- **One width system:** every standard page uses the same max-width + gutter;
  immersive pages get consistent full-bleed padding. (Done: removed
  `isWideWorkspace` fork.)
- **One first-run gate:** onboarding redirect applies to all roles. (Done.)
- Keep skip link, `#main-content`, theme init, transparency-notice gate.

### 5. Medicines consolidation
- `/medicines` becomes a hub with `Tabs`: **Danh sách** (confirmed list + DrugBank
  DDI, today's `/medicines`), **Tủ thuốc** (cabinet + OCR, today's `/selfmed`),
  **An toàn** (interaction/allergy analysis, today's `/careguard`).
- `/selfmed`, `/selfmed/*`, `/careguard` become thin redirects to the corresponding
  hub tab (Next.js `redirect()` stubs), preserving deep links (Req 2.2).
- All existing client logic modules (`lib/selfmed*`, `lib/careguard*`,
  `lib/medication-courses`) are reused unchanged; only composition/presentation
  changes. Consent gate + disclaimers + low-confidence confirm preserved.

### 6. First-run & empty states
- `/welcome` (built) is the single first-run flow for all roles.
- Standardize every data page on `AsyncSection` + `EmptyState` with a primary CTA.

## Data Models
No new persistent data models. The onboarding `phr_profiles.onboarding_*` columns
(migration `0029`) already exist. Navigation/IA is a static config; tabs are client
state.

## IA: before → after

| Before (issue) | After |
| --- | --- |
| `/selfmed`, `/medicines`, `/careguard` as 3 sibling nav items (overlap) | One **Medicines** hub with 3 tabs; old routes redirect |
| `/research` + `/evidence` both under "research" (blurred) | Keep both but relabel: Research = ask/synthesize; Evidence = tracked living-evidence questions; grouped under **Explore** |
| `/today` + `/dashboard` + `/lifemap` overlap for consumers | Consumer home = **Today**; `/dashboard` stays clinician/admin-only (already `hiddenForRoles: normal`); LifeMap = the map |
| 4 hand-maintained nav renderers, 2 active-state styles | 1 model + shared `<NavItem>`, 1 active style |
| Nav labels mix internal names | User-facing labels only for consumers |

## Correctness Properties
- **P1 (width invariance):** for any two standard routes, the content column max-width
  and gutter are identical.
- **P2 (redirect preservation):** every removed/moved route resolves (via redirect) to
  its consolidated destination; no consumer deep link 404s.
- **P3 (token-only color):** no redesigned surface introduces a hardcoded hex color
  utility (token regression guard).
- **P4 (AA contrast):** every used fg/bg token pair meets its AA threshold.
- **P5 (focus visible):** every interactive control shows the shared focus ring, incl.
  forced-colors.
- **P6 (role gating unchanged):** nav entries and route access match the pre-redesign
  RBAC arrays exactly.
- **P7 (first-run universality):** any role with `needs_onboarding` is routed to
  `/welcome`.

## Testing Strategy
- Reuse and keep green: `contrast.test.ts`, `focus-accessibility.test.ts`,
  `design-tokens.test.ts`, `chat-shell-theme.test.ts`, `navigation.config.test.ts`,
  `app-shell.test.tsx`.
- Add: nav-model grouping/role tests for the new IA; redirect tests for consolidated
  routes; a width-consistency assertion; a Medicines-hub tab test.
- Gate each phase on `npm run lint`, `npm run test`, `npm run build`; deploy only when
  green.

## Rollout (reversible phases)
1. Foundations — tokens/legacy reconcile, primitives (`Tabs`/`Modal`/`Toggle`),
   width + gate fixes (partially done).
2. Navigation model + shared renderers + goal-oriented IA.
3. Medicines consolidation + redirects.
4. Page adoption sweep (remaining bespoke pages → primitives, empty states).
5. First-run + polish + a11y pass.
6. Full validation + deploy.
