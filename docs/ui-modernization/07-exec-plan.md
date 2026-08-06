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

- [ ] Add semantic token aliases and update token/contrast tests.
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

Validation: type-check, lint (existing warnings only), route matrix 79/79, i18n 3,271 pairs, full unit suite 92 files/701 tests, production build 91 routes, bundle +0.29%, and dashboard E2E 8/8. Rollback is a single dashboard checkpoint revert; there is no schema migration.

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
