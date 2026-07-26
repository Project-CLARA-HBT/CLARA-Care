# CLARA Web — Fluent Design-System Modernization

Date: 2026-07-26
Status: Implemented (foundation + shared primitives + consumer core pages)
Scope: `apps/web` visual language, shared UI primitives, and the LifeMap
consumer core surfaces (Today, LifeMap, Medicines).

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

## 7. Follow-ups (not in this pass)

- Migrate remaining professional surfaces (Dashboard, Visits, Family, Scribe,
  Council, Research) to the shared primitives.
- Reconcile the two nav active-state color systems (mobile `sky-*` vs desktop
  `--brand-*`) onto a single token.
- Retire the neutralized dead glass/glow/gradient CSS once no surface depends
  on those class names for layout.
- Replace the FontAwesome 4.7 CDN dependency (theme-toggle icons) with Material
  Symbols to consolidate on one icon system.
