# Implementation Plan — CLARA UI/UX Redesign

Each task keeps the app building and green. Safety-locked tests
(contrast/focus/tokens/nav/chat-theme) are the gate. Deploy only when green.

## Phase 1 — Foundations
- [x] 1.1 Design tokens: tinted canvas, distinct elevation tiers, refined brand ramp,
  layered shadow scale, radius + type scale, Inter webfont. _Req 3.1, 3.4_
- [x] 1.2 Remove dead FontAwesome CDN dependency. _Req 3.2, 8.4_
- [x] 1.3 Shared primitives: Button, Field/Select/Textarea, Badge,
  SurfaceCard/StatCard/EmptyState/InlineError/LoadingCards. _Req 4.1_
- [x] 1.4 Unify content width across all standard pages (remove `isWideWorkspace`
  fork). _Req 1.1, 1.4_
- [x] 1.5 Apply first-run onboarding gate to all roles. _Req 6.1, 6.4_
- [x] 1.6 Add `Tabs`, `Modal`, `Toggle` primitives (token-driven, a11y, reduced
  motion). _Req 4.1, 4.4, 5.x_
- [ ] 1.7 Reconcile remaining legacy CSS: neutralize/remove dead glass/glow/gradient
  rules and the unused `medical` palette + `sky/teal/cyan→blue` Tailwind aliases,
  without regressing contrast/focus/chat-theme tests. _Req 3.2, 8.1, 8.4_

## Phase 2 — Navigation & IA
- [x] 2.1 Regroup `navigation.config.ts` into goal-oriented groups (Care, Medicines,
  Explore, Clinical, Admin, Support) with consumer-friendly labels; preserve RBAC
  role arrays, `PUBLIC_ROUTES`, `isActiveRoute`, `resolvePostLoginPath`,
  `isAuthenticatedUtilityRoute`. _Req 2.1, 2.4, 8.1, 8.2_
- [x] 2.2 Extract a shared `<NavItem>` + one active-state style; refactor sidebar,
  mobile drawer, bottom-nav, and topbar to consume `getGroupedNavItems(role)`.
  _Req 2.5, 4.2, 4.3_
- [x] 2.3 Update/extend `navigation.config.test.ts` for the new grouping; assert role
  gating is byte-for-byte unchanged. _Req 8.2_

## Phase 3 — Medicines consolidation
- [x] 3.1 Build `/medicines` hub with `Tabs`: Danh sách (list + DDI), Tủ thuốc
  (cabinet + OCR), An toàn (interaction analysis); reuse existing lib modules and
  preserve consent gate + disclaimers + low-confidence confirm. _Req 2.2, 7.x_
- [x] 3.2 Convert `/selfmed`, `/selfmed/add`, `/selfmed/ddi`, `/careguard` to redirect
  stubs into the correct hub tab; add redirect tests. _Req 2.2, 2.3_
- [x] 3.3 Remove the now-duplicate medication nav items; keep one **Medicines** entry.
  _Req 2.1, 2.2_

## Phase 4 — Page adoption sweep
- [x] 4.1 Migrate any remaining bespoke-styled pages to primitives + tokens (audit for
  hardcoded hex, raw palette, inline control strings). _Req 3.3, 4.1, 8.4_
- [~] 4.2 Standardize data pages on `AsyncSection`/state primitives + `EmptyState`.
  Consumer/feature pages use the shared state primitives; a full AsyncSection
  sweep of admin analytics pages remains optional follow-up. _Req 6.2, 6.3, 4.4_
- [x] 4.3 Replace bespoke modals (e.g. community compose) with the `Modal` primitive.
  _Req 4.1, 5.2_

## Phase 5 — First-run & polish
- [x] 5.1 Polish `/welcome` copy/visuals; ensure skip + resume + completed→home paths.
  _Req 6.1, 6.4, 6.5_
- [x] 5.2 Accessibility pass: focus order, labels, `aria-*`, reduced-motion, forced
  colors across redesigned surfaces. _Req 5.1–5.5_
- [x] 5.3 Responsive pass: mobile/tablet/desktop for shell + hub + key pages
  (content padding, scrollable tabs, bottom-nav shortLabels, responsive titles). _Req
  1.2, 1.3_

## Phase 6 — Validation & deploy
- [x] 6.1 Full gate: `npm run lint`, `npm run test`, `npm run build` green; added
  width-consistency + medicines redirect/hub-tab tests. _Req 8.3_
- [x] 6.2 Deploy web to VPS; verified health, first-run gate for all roles, medicines
  hub tabs, and consolidated redirects live. _Req 8.5_
- [x] 6.3 Update `docs/design/clara-ui-modernization-*` with the final system + IA map.

## Phase 7 — IA alignment with product definition (LifeMap spec §6.1)
- [x] 7.1 Demote Chat from primary IA: brand mark + consumer bottom nav lead with
  Today/LifeMap; Chat stays reachable via the topbar/sidebar "Hỏi CLARA" action
  (spec: chat is an input/explanation surface, not the IA). _Req 2.1, 2.4_
- [x] 7.2 Flag-gate `/community` (only shown when `NEXT_PUBLIC_SOCIAL_PLATFORM_ENABLED`
  is on), matching the fail-closed social design; removed the permanently-hidden
  dead nav entry. _Req 2.1, 8.1_
- [x] 7.3 Consumer mobile primary nav = Today · LifeMap · Hồ sơ · Thuốc (Chat is the
  persistent quick-ask action, not a tab); locked with a nav test. _Req 1.2, 2.1_
- [x] 7.4 Remove dead nav helpers (`getTopNavLinks`, `GROUP_LABELS`) no component
  consumed. _Req 8.4_
