# UI Modernization ExecPlan

## Purpose

Deliver a modern, task-first, accessible CLARA web experience while preserving every authorized capability and all medical/privacy invariants. This document is executable progress, not a static proposal.

## Current-state summary

See `00-current-state-audit.md`. Baseline lint/type/unit/build passed; synthetic screenshots are under `evidence/baseline/`. Seven specialist audits completed. The working tree contains unrelated user-owned changes that must not be staged or rewritten.

## Milestones and gates

### M0 — Audit and specification

- [x] Read repository guidance, source, route config, tests, CSS, API-facing clients.
- [x] Spawn and receive audits A–G.
- [x] Capture synthetic baseline screenshots and record limitations.
- [x] Create docs 00–11 and root planning guidance.
- [x] Three independent planning reviews received; resolutions are recorded in `11-decisions-and-progress.md`.
- [x] Add `PLANNING_GATE: PASSED` after executable-gate changes and route/contract resolutions are verified.

Validation: docs links/path check, baseline lint/type/unit/build/E2E evidence. Baseline E2E command `cd apps/web && npm run test:e2e` ran on 2026-08-06 against the production standalone server: 6 passed, 2 failed, 2 skipped in 2m3s. Failures are stale shell assertions (`Mở CLARA Chat`, mobile `Open navigation menu`) and are recorded repair work, not ignored.

### M1 — Foundations

- [x] Apply the canonical Clara Health System deep-well aliases to the shared shell and set the default preference to dark.
- [x] Add typed SVG Icon and fallback; fix PHR raw icon regression.
- [ ] Harden Field, Alert/LiveStatus, SideSheet, ConfirmDialog, and touch targets.
- [ ] Add primitive tests.

Validation: format/lint/type/unit, i18n/terminology, focused a11y tests, build.
Rollback: revert M1 commit; retain old primitive exports and font compatibility.

### M2 — Shell and navigation

- [x] Split route/access/navigation/alias registries.
- [x] Add workspace derivation/switcher and More model.
- [x] Extract shell presentation; remove duplicate Chat/profile/logout controls.
- [x] Replace mobile drawer with tested focus trap/More navigation and preserve collapse preference.

Pre-M2 capability reachability gate: generate and test `route-capability-matrix.md`, classify every route/alias, separate access from presentation, verify all role/flag combinations and legacy URLs, then change the menu. No sidebar refactor begins before this gate.

Validation: role/flag matrix, direct/forbidden routes, public shell-free paths, responsive E2E, build.
Rollback: revert M2 or set short-lived shell flag; both paths use the same access module.

### M3 — Personal workspace

- [x] Make Overview honest and Today task-first.
- [ ] Migrate LifeMap creation/episode details progressively.
- [x] Convert Visit preparation to focused steps while preserving current API.
- [x] Convert Family to tabs and explicit share review.
- [x] Complete PHR detailed states: record-derived ProgressList, identity/contact-insurance, paired body-measurement history/BMI, allergy/condition/medication empty and populated views, provenance-preserving editing, and mobile review.
- [x] Remove duplicate Medicines CTAs; preserve course/cabinet/DDI distinction and keep CareGuard as the canonical DDI surface.

PHR detail checkpoint (2026-08-06): the supplied detail designs now map to separate identity, body, contact/insurance, allergy, condition, medication and responsive overview states. Paired body measurements are server-derived; empty panels contain no demo clinical data; an explicit no-known-allergy declaration persists immediately; inactive medicines remain retained and can be restored to current use. The mobile overview intentionally condenses the six desktop sections into four data-derived cards without removing the direct section routes.

Validation: state matrices, consent/provenance/safety tests, personal E2E, visual matrix.
Rollback: per-route revert; keep aliases and shared domain components.

### M4 — Chat and research

- [x] AppShell is sole global shell.
- [ ] History/workspace are mutually exclusive disclosures.
- [x] Answer-first hierarchy and progressive explainability disclosure.
- [ ] Role-aware expert/admin diagnostics; Research remains Chat mode.
- [ ] Source Hub browse/sync separation and Evidence steps.

Validation: citation, role/privacy, deep-link, chat parity, visual/a11y/E2E.
Rollback: preserve Chat V2 flag and legacy route.

### M5 — Clinical/Council/Scribe

- [x] Add visible canonical Scribe stages while preserving server consent/sign semantics.
- [x] Bring Council into the shared page heading/surface hierarchy.
- [ ] Shared Council case context and result hierarchy.
- [ ] Shared primitives and shell; technical detail progressive.

Validation: clinician safety, consent, audit, no-CoT/confidence, E2E and mobile reflow.

### M6 — CSS cleanup and compatibility

- [ ] Inventory and remove only verified-dead selectors/components.
- [ ] Keep rollback/alias styles until retirement criteria are met.
- [ ] Add bundle and hydration/console checks.

Validation: clean build, bundle budget, visual diff, route inventory, docs-check.

### M7 — Final quality and release evidence

- [ ] Independent architecture, UX, accessibility, regression, medical-safety reviews.
- [ ] Repair all Critical/High findings; record Medium/Low decisions.
- [ ] Full web tests/build/E2E/a11y/visual/bundle/i18n/terminology.
- [ ] Capture after screenshots and update traceability.
- [ ] Commit stable checkpoints; push/PR/deploy only after explicit final evidence.

## Decision log

1. Preserve all capabilities via More/context/direct links; no flat-menu deletion.
2. Do not invent patient directory or Admin Settings route absent backend support.
3. Keep medication data models distinct until canonical mapping exists.
4. Keep Chat rollback and legacy CSS until parity evidence exists.
5. Treat raw icon names, synthetic Dashboard metrics, and Scribe consent/sign ambiguity as high-priority fixes.
6. No DB migration is required for the presentation milestones; optional API hardening is isolated and cannot be presented as saved functionality until contract evidence exists.

## Planning gate

`PLANNING_GATE: PASSED` on 2026-08-06. The three review resolutions, exhaustive 79-route matrix, contract-readiness boundaries, executable route/bundle checks, baseline E2E evidence, accessibility/visual smoke harness, and safety/privacy acceptance additions are verified. The initial rollback is milestone revert; no shell kill switch is claimed until implemented.

## Surprises/discoveries

- Existing documentation claimed a previous redesign was complete, but audits found menu/access coupling, raw icon failure, mobile focus gaps, and several overloaded flows.
- Local Node is 24 while CI implies Node 20; runtime pinning is required before relying on local-only behavior.
- The task had no accessible screenshots; synthetic baseline evidence is explicit.
- Build and unit baseline are green despite the UX/a11y findings, so new tests must target behavior not covered by compilation.

## Progress update protocol

After every milestone, update this file, `08-task-list.md`, and `11-decisions-and-progress.md` with commit, files, tests, failures/repairs, and rollback state. Never mark a task complete because a skeleton compiles.

## Dashboard visual follow-up — 2026-08-06

- [x] Rebuilt `/dashboard` from the supplied visual hierarchy without copying external fonts, icon fonts, avatars, or synthetic health data.
- [x] Kept the route professional-only and made shortcuts role-aware for researcher, doctor, and admin workspaces.
- [x] Preserved structured alert severity/message/destination through normalization and rendered the highest-priority alert before ordinary tasks.
- [x] Removed health-reassuring inference from empty/loading/error operational data.
- [x] Replaced dark-unsafe brand shades with the semantic `--text-brand` token and repaired mobile badge reflow.
- [x] Added focused normalizer/data-integrity tests plus an eight-case Playwright matrix and four screenshot artifacts.

## Design-system shell checkpoint — 2026-08-07

- [x] Mapped every supplied design family to its route(s) in `12-design-route-map.md`; no design reference is allowed to imply a route or capability absent from the product.
- [x] Made the canonical Clara Health System dark palette the initial shared theme, including the exact deep-well surface stack, primary/secondary/error status tones, Be Vietnam Pro scale, 256px desktop navigation and 1120px desktop canvas.
- [x] Removed light gradients, elevated shadows and the personal-workspace selector from the shared shell; professional workspace switching remains available so route access is not affected.
- [x] Reskinned common cards, navigation states, Council panels and Scribe primary actions to use shared tonal layers instead of local white/slate treatments.

Validation: `cd apps/web && npm run lint` passes with seven pre-existing React Hook dependency warnings only. Rollback: revert this web-only checkpoint; no API, schema, consent, RBAC or CSRF behavior changed.

## PHR and Council screen-surface checkpoint — 2026-08-07

- [x] Converted the actual PHR detail surfaces for sharing, FHIR export, emergency-card preview, reminders and OCR review from legacy white/slate/sky treatments to the supplied deep-well card, control, status-chip and error palette.
- [x] Converted the Council result flow canvas itself (not the shared shell) to the supplied 14px card frame, tonal canvas and canonical primary/warning/error states; no visual-only green clinical-success signal is introduced.
- [x] Kept all PHR mutation, consent, share scope/revocation, OCR manual-confirmation, Council emergency and backend authorization behavior untouched.

Validation: `npm run lint` passes with the seven tracked pre-existing hook warnings; focused PHR/Council tests pass 23/23. Rollback: revert the component-only checkpoint; no API/schema/safety-policy changes.

## Medicines consent-state screen checkpoint — 2026-08-07

- [x] Aligned the real consent-required medicines screen, including legal links, disabled state, error/retry boundary and primary acknowledgement control, with the canonical dark surface and status colors.
- [x] The screen remains a backend-gated consent step; this checkpoint changes no acceptance logic, request, CSRF protection or medical-data access rule.

Validation: focused Medicines tests pass 7/7. Rollback: component-only revert.

## Research workspace screen checkpoint — 2026-08-07

- [x] Aligned the live Research Workspace's frame/search/synthesis/watch states: page width, stage tabs, form focus, clarification boundary, results rail and primary action now use the supplied tonal card system instead of a gradient/light-blue treatment.
- [x] Source selection, upload, job execution, clarification and result handling remain unchanged and are still available only through their existing route/role contract.

Validation: focused Research tests pass 31/31; lint passes with the seven tracked pre-existing hook warnings. Rollback: component-only revert.

## CSRF profile-save repair — 2026-08-07

- [x] Reproduced the production cookie-auth boundary: a PHR save without the header is 403; the matching double-submit token is 200; a browser login and identity-save smoke succeeds.
- [x] Changed the browser CSRF cookie reader to select the final duplicate-name cookie, matching the API parser and preventing stale pre-domain-migration cookies from generating a false CSRF failure.
- [x] Preserved CSRF enforcement; no mutation route was exempted and no authorization/consent behavior changed.

Validation: focused auth-store/http-client/PHR tests pass 10/10; lint passes with the seven tracked pre-existing hook warnings. Rollback: revert the client reader and its regression test.

## Council empty-state E2E repair — 2026-08-07

- [x] Replaced the latest-case 404 request in the three Council result/workspace entry points with an owner-scoped one-item list query; an empty history is now a normal empty state rather than an API error.
- [x] Clears an obsolete locally remembered case id when no owner-scoped case remains; no other user's data is requested or inferred.

Validation: focused Council tests pass 10/10 and web type-check passes. Rollback: revert the web-only empty-state adapter.

Validation: type-check, lint (existing warnings only), route matrix 79/79, i18n 3,271 pairs, full unit suite 92 files/701 tests, production build 91 routes, bundle +0.29%, and dashboard E2E 8/8. Rollback is a single dashboard checkpoint revert; there is no schema migration.

## LifeMap and operational-visualization checkpoint — 2026-08-08

- [x] Reordered `/lifemap` around the actual open journeys and accepted Today tasks returned by the profile-scoped LifeMap projection. The first-use state now leads only to the existing guided journey flow; it does not expose task creation before an episode exists.
- [x] Kept replay, question, provenance, capture, review and visit-preparation capabilities intact as contextual lower-level panels. No task count, progress, duration or health state is fabricated: every displayed task is returned by `getLifeMapToday`.
- [x] Updated Dashboard/Admin shell and chart frames to use the canonical deep-well tonal card system rather than local glow/neon styling.
- [x] Removed unsupported observability copy that implied a fixed ML node count or an estimated p95 value. The console now labels derived indices as derived and describes average latency only when returned by telemetry.

Validation: targeted LifeMap and Admin observability tests pass 7/7; lint and TypeScript checks pass for all changed web surfaces. Rollback: revert this UI-only checkpoint; LifeMap mutations, profile scope, consent, telemetry collection and route authorization are unchanged.

## Council and Scribe workflow-surface follow-up — 2026-08-08

- [x] Replaced the gradient Council case-creation/result actions with canonical solid primary controls and converted warning/escalation panels to the shared semantic danger/warning tokens.
- [x] Aligned the active Scribe workspace header, tabs, session list and first-use session panel with the same deep-well card stack; recording consent, WebAudio capture, transcript, draft SOAP and finalize contracts are untouched.

Validation: targeted Scribe integration/regression tests pass 7/7; Council/Scribe lint and TypeScript checks pass. Rollback: component-only revert; no clinical-generation, consent or signing behavior changed.

## Ecosystem operational surface follow-up — 2026-08-08

- [x] Began the dashboard ecosystem visual migration from local slate/white/gradient treatments to canonical deep-well surfaces and semantic status colors.
- [x] All values, bars and summary states remain bound to the existing `getSystemEcosystem` snapshot. Missing values continue to render as unavailable rather than as fabricated operational measurements.

Validation: Ecosystem lint and TypeScript checks pass. Rollback: page-only revert; no system telemetry or operator action contract changed.

## Dashboard responsive evidence refresh — 2026-08-08

- [x] Ran the production-artifact Dashboard Playwright suite after the visual checkpoints across 1440×900, 1280×800, 768×1024 and 390×844.
- [x] All eight state/viewport checks passed. The suite verifies real structured-alert prioritization, non-reassuring failure copy, authorized shortcut presentation and horizontal-overflow limits; screenshots are in `apps/web/test-results/dashboard-*.png` and remain synthetic/no-PII.

Validation: `npm run test:e2e -- e2e/dashboard.spec.ts` passes (8/8). Rollback: no behavior change; this is release evidence only.

## Today real-data state follow-up — 2026-08-06

- [x] Rebuilt `/today` around the supplied active, completed, and first-time hierarchy using only server-returned LifeMap data.
- [x] Added a read-only, profile-scoped Today projection for completed tasks in the current local day and previous six local days; it changes no LifeMap event, revision, provenance, confirmation, or task transition.
- [x] Sent the user from an open task to its existing detail/confirmation screen; completion remains an explicit versioned mutation with `If-Match` and an idempotency key.
- [x] Added an honest caught-up state for an open journey without a current task. No durations, steps, medicines, progress percentages, or clinical status are invented.
- [x] Replaced the last remaining font-dependent mobile bottom-nav glyph and mobile notification glyph with bundled typed SVG icons after four-viewport E2E exposed 22–23px horizontal overflow before the external font loaded.

Validation: API LifeMap foundation contracts 4/4; Ruff; web type-check; i18n contract; full web unit suite 92 files/702 tests; production build (91 routes); and `/today` E2E 12/12 across desktop, laptop, tablet, and mobile. Existing unrelated React Hook lint warnings remain build warnings. Rollback is a single checkpoint revert; no schema migration is needed.

## Chat visual-system checkpoint — 2026-08-06

- [x] Applied the Clara Health System dark token palette and Be Vietnam Pro at the shared token layer; light-mode tokens remain unchanged.
- [x] Kept Chat answer-first and removed the duplicate Research topbar link; Research remains a real Chat response mode.
- [x] Rendered a calm, explicit insufficient-evidence state from the actual evidence-release result. It offers the existing visit-preparation route, never an invented source, diagnosis, appointment, or clinical conclusion.
- [x] Kept one canonical source disclosure whenever a citation registry exists, preserved inline source anchors, and retained role-gated diagnostics plus no-CoT filtering.
- [x] Migrated high-frequency Chat welcome/sidebar/shared-button icons to bundled SVG output to prevent raw icon-name flashes.

Validation: token/contrast tests, Chat canvas/welcome/composer/shell tests, i18n and TypeScript checks. Rollback: `NEXT_PUBLIC_CHAT_V2=false` selects the preserved legacy Chat, or revert this web-only checkpoint. No schema/API contract changed.

## Mobile compile and terminology-regression checkpoint — 2026-08-08

- [x] Repaired two mobile Dart syntax regressions in the LifeMap capture/source
  preview and Living Evidence interval menu. These were missing widget
  closers/interpolation boundaries, not product-flow changes.
- [x] Made Cabinet OCR default to the documented Vietnamese consumer locale
  when no app-level preference is supplied, while passing the existing shared
  `LanguageController` preference from the Cabinet screen when available.
- [x] Updated Home redesign expectations to current consumer terminology and
  preserve the fail-closed assertion: duplicated Chat wording represents two
  intentional reachable actions rather than a privileged-card leak.

Validation: focused Home/a11y tests 8/8 and Cabinet OCR safety tests 4/4 pass.
`flutter analyze` has no errors; it reports four pre-existing informational
deprecations/dangling-doc notices outside these surfaces. Rollback: revert the
mobile component/test checkpoint; no server contract, consent, RBAC, OCR
manual-confirmation gate or medication write behavior changed.
