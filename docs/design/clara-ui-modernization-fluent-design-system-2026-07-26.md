# CLARA Web — Fluent Design-System Modernization

Date: 2026-07-26
Status: Implemented (foundation + shared primitives + full page adoption +
IA regroup + medicines consolidation + first-run onboarding + mobile pass)
Scope: `apps/web` visual language, shared UI primitives, navigation IA, and the
authenticated app surfaces. See also `.kiro/specs/clara-ui-ux-redesign/`.

## 1. Why

The web app had accumulated three overlapping styling systems (custom `.app-*`/
`.fluent-*` classes, CSS-token utilities, and raw Tailwind palette colors),
a half-finished "glass → Fluent" migration that shipped dead decorative CSS,
no brand typeface, flat white-on-white surfaces, an undefined `--shadow-sm`
token (so the most-used card rendered with no shadow), and no shared
`Button`/`Field`/`Badge` primitives. The result read like an unstyled internal
tool rather than a modern consumer health product.

This change establishes a single, coherent, accessible Fluent-inspired design
system and applies it to the consumer core, without weakening any safety,
consent, telemetry, or accessibility invariant.

## 2. Non-negotiable invariants preserved

- **WCAG AA contrast** — all AA-locked token pairs in
  `styles/contrast.test.ts` are unchanged in value and still pass.
- **Focus + skip link** — the `--focus-ring-*` tokens, global `:focus-visible`
  outline, forced-colors handling, and skip-link contract
  (`styles/focus-accessibility.test.ts`) are unchanged.
- **Chat theme integration** — the `.clara-chat-v2` canvas/sidebar token
  contract (`styles/chat-shell-theme.test.ts`) is unchanged.
- **Design-token surface audit** — no hardcoded hex utilities introduced;
  `styles/design-tokens.test.ts` still passes.
- No change to safety copy, consent gating, RBAC, or telemetry.

## 3. Foundation (`styles/globals.css :root`)

### Typography
- Brand typeface **Inter** loaded via Google Fonts in `app/layout.tsx`, with a
  Segoe UI Variable → system-ui fallback chain (graceful on Linux/macOS where
  Segoe is absent). `--font-sans` and `--font-display` lead with Inter.
- Formal type scale tokens: `--text-display`, `--text-title`, `--text-heading`,
  `--text-body`, `--text-caption` (display/title are fluid `clamp()`).

### Elevation and surfaces
- Real light-mode elevation tiers: `--bg-elev-1 #ffffff`, `--bg-elev-2 #fbfcfe`,
  `--bg-elev-3 #f6f8fc`, over a slightly cooler canvas `#eef1f7` so cards read
  as raised rather than dissolving into a near-white page.

### Radius
- Softer, more modern radii: `sm 8`, `md 12`, `lg 16`, `xl 24`, plus new
  `--radius-2xl 28` and `--radius-pill 999`.

### Shadows
- Added the previously-missing `--shadow-sm`.
- Rebuilt `--shadow-soft/float/hero` as layered, low-contrast Fluent depth
  (cool slate tint, tight ambient + soft directional) instead of the old
  hard black double-drop.

## 4. Shared primitives (`components/ui`)

All primitives are token-driven, keyboard-accessible (reuse `.focus-ring`),
respect `prefers-reduced-motion`, and meet the 44px touch-target minimum.

- **`button.tsx`** — `Button` (default + named export). Variants
  `primary | secondary | ghost | danger`; sizes `sm | md | lg`; `block`,
  leading/trailing `icon`, `loading` + `loadingLabel` (spinner + `aria-busy`),
  and an `as="link"` mode that renders a Next `Link` with identical styling.
- **`field.tsx`** — `Field` (input), `Textarea`, `Select`. Auto-associated
  `<label>` via `useId`, consistent control styling, `optional` hint, hover +
  token focus states.
- **`badge.tsx`** — `Badge` with tones `neutral | brand | ok | warn | danger`
  mapped to the `--status-*` triads; optional leading icon; pill radius.
- **`surface.tsx`** — `SurfaceCard` (optional `interactive` lift-on-hover),
  `StatCard` (label/value/hint/icon with tone ring), `InlineError` (token
  danger styling + retry), `LoadingCards` (skeleton grid), `EmptyState`
  (icon chip + title + description + action slot).
- `components/lifemap/lifemap-primitives.tsx` now re-exports from
  `components/ui/surface.tsx` for backward compatibility, so every existing
  importer inherits the upgraded styling with no churn.

## 5. Applied surfaces

- **`app/today/page.tsx`** — rebuilt with `StatCard` metrics, `SurfaceCard`
  task list, `Button` (incl. `as="link"` empty-state CTA); JSX de-densified
  into readable, maintainable markup.
- **`app/lifemap/page.tsx`** — `Field`/`Textarea`/`Select`/`Button` forms,
  `Badge` priorities, `SurfaceCard`/`EmptyState`; removed ~200-char inline
  input class strings.
- **`app/medicines/page.tsx`** — same primitive set; status pills moved from
  raw `bg-emerald-*`/`bg-amber-*` Tailwind to tone-mapped `Badge`/token
  surfaces.

## 6. Validation

- `npm run lint` — passes (pre-existing warnings only).
- `npm run test` — 559/559 pass, including all style invariant suites.
- `npm run build` — production build succeeds; `/today`, `/lifemap`,
  `/medicines` compile.

## 7. Follow-up pass (2026-07-26) — completed

The deeper UX/IA redesign (spec: `.kiro/specs/clara-ui-ux-redesign/`) landed on
top of the foundation above:

- **All pages migrated** to the shared primitives + tokens; no hardcoded hex or
  raw Tailwind palette colors remain on page/component surfaces.
- **Single nav active-state system.** A shared `<NavItem>` (`components/
  navigation/nav-item.tsx`) now feeds the desktop sidebar, mobile drawer, and
  bottom bar from `getGroupedNavItems(role)`, replacing four hand-maintained
  renderers and the dual `sky-*` vs `--brand-*` active styles.
- **FontAwesome 4.7 removed** — the app is now on a single icon system
  (Material Symbols).
- **Dead Tailwind palette removed** — the `sky/teal/cyan → blue` aliases and the
  unused `medical` teal palette are gone from `tailwind.config.ts`.
- **New primitives**: `Tabs`/`TabPanel`, `Modal` (focus-trap, Escape, scroll
  lock, restore focus), `Toggle` (`role="switch"`). Community compose now uses
  `Modal`; `/welcome` uses `Toggle`.
- **Unified content width** — every non-immersive page shares one centered
  `max-w-[1200px]` column (guarded by `components/content-width.test.ts`); the
  old `isWideWorkspace` fork that made page widths jump is gone.
- **First-run onboarding** — `/welcome` flow gated for all roles.
- **Mobile pass** — scrollable tablist, bottom-nav `shortLabel`s, roomier
  content padding, responsive page titles, tokenized scrims.

### Information architecture (final)

Goal-oriented nav groups (`navigation.config.ts`), role-gated:

| Group | Consumer label | Key routes |
| --- | --- | --- |
| care | Chăm sóc của bạn | `/chat`, `/today`, `/lifemap`, `/visits`, `/family`, `/phr`, `/dashboard`* |
| medicines | Thuốc & an toàn | `/medicines` (hub: Thuốc / Tủ thuốc / An toàn) |
| explore | Khám phá & bằng chứng | `/research`, `/evidence`, `/research/source-hub` |
| clinical | Lâm sàng | `/council`, `/scribe` |
| admin | Vận hành | `/admin/*` |
| support | Trợ giúp & tài khoản | `/huong-dan`, account/consent/data (flag-gated) |

*`/dashboard` hidden for `normal`.

**Medicines consolidation**: `/selfmed`, `/selfmed/ddi`, `/careguard` are now
redirect stubs into the correct `/medicines?tab=` panel, collapsing three
overlapping medication surfaces (and three nav entries) into one hub.

### Remaining optional follow-ups

- Retire the neutralized dead glass/glow/gradient CSS class names once no
  research/dashboard/council surface depends on them for layout.
- Standardize every data page on `AsyncSection` (some still use the
  `LoadingCards`/`InlineError`/`EmptyState` trio directly).
