# Reviewable task list and traceability

Status values: `pending`, `in_progress`, `blocked`, `done`. Owners are bounded implementation/review roles; the root agent integrates all diffs.

## Tasks

| ID | Requirements | Objective | Owner | Dependencies | Likely files | Acceptance/tests | Status |
|---|---|---|---|---|---|---|---|
| UI-01 | NFR-MAINT-001 | Pin Node/npm metadata and add explicit web type-check script. | Foundation | baseline | `.nvmrc`, `apps/web/package.json`, CI | npm ci, type-check, build | done |
| UI-02 | NFR-THEME-001, NFR-A11Y-001 | Add semantic token aliases and update contrast/focus guards. | Foundation | UI-01 | `styles/*`, `tailwind.config.ts` | token/contrast tests, light/dark visual | done |
| UI-03 | FR-PHR-002 | Implement typed SVG Icon/fallback and migrate PHR/shared primitives. | Foundation | UI-02 | `components/ui/icon.tsx`, `app/phr/page.tsx` | icon unit/E2E with fonts blocked | done |
| UI-04 | NFR-A11Y-002, NFR-A11Y-003 | Harden Field, Alert, SideSheet, ConfirmDialog and 44px targets. | Foundation | UI-02 | `components/ui/*`, dialogs | component focus/semantics tests | pending |
| UI-05 | FR-NAV-001–006 | Create exhaustive route capability manifest, then split route/access/navigation/legacy registries and add workspace model. | Shell | UI-01 | `lib/navigation*`, `route-capability-matrix.md`, new registry files | route classification, role/flag/property/redirect tests | done |
| UI-06 | FR-SHELL-001–006 | Extract shell presentation and profile/workspace providers. | Shell | UI-04/UI-05 | `components/app-shell.tsx`, navigation | shell unit/E2E, public/401 tests | done |
| UI-07 | FR-SHELL-005 | Replace mobile drawer with SideSheet and add More/bottom nav. | Shell | UI-04/UI-06 | `app-shell.tsx`, navigation | focus/restore/mobile E2E | done |
| UI-08 | FR-TODAY-001/002, FR-OVR-001 | Remove fabricated dashboard fallback; make Today task-first with truthful active/completed/first-time/caught-up states. | Personal | UI-06 | dashboard/today pages, LifeMap Today projection | API contract, state tests, four-viewport personal E2E | done |
| UI-09 | FR-LIFE-001–004 | Progressive LifeMap creation and episode presentation without truth changes. | Personal | UI-04/UI-06 | lifemap routes, guided flow | wizard/state/safety E2E | pending |
| UI-10 | FR-VISIT-001/002 | Focused Visit preparation steps and contextual consent. | Personal | UI-04/UI-06 | visits routes/components | integration/E2E | done |
| UI-11 | FR-FAM-001/002 | Family URL-backed tabs and explicit invitation review. | Personal | UI-04/UI-06 | family routes/components | tabs/share/revoke E2E | done |
| UI-12 | FR-PHR-001/003 | PHR ProgressList, detailed record sections, body-measurement history/BMI, conflict-safe presentation and per-screen deep-well visual parity. | Personal | UI-03/UI-04 | phr routes/components, PHR observations API | form/provenance/a11y/API tests, responsive mobile overview | done |
| UI-13 | FR-MED-001–004 | Medicines first-run/CTA hierarchy and distinct model copy. | Personal | UI-03/UI-04 | medicines pages/components | flow/safety E2E | done |
| UI-14 | FR-CHAT-001–005 | Chat two-column answer-first disclosure and role-gated diagnostics. | Chat | UI-04/UI-06 | `app/chat/_v2/*` | parity/privacy/citation/E2E | done |
| UI-15 | FR-EVID-001, FR-RES-001 | Evidence step disclosure and Source Hub browse/sync split. | Chat | UI-14 | evidence/research routes | release-gate/citation tests | pending |
| UI-16 | FR-COUNCIL-001–003 | Council case context, result hierarchy and canonical deep-well flow canvas. | Clinical | UI-04/UI-06 | council routes/components | safety/role/E2E | in_progress |
| UI-17 | FR-SCRIBE-001–003 | Canonical Scribe stages, consent and sign semantics. | Clinical | UI-04/UI-06 | scribe page/components/libs | workflow/safety/E2E | in_progress |
| UI-18 | NFR-PERF-001/002 | Add bundle budget, console/hydration, visual and axe E2E. | Test | UI-03/UI-07 | scripts, `e2e/*`, config | four viewport matrix | done |
| UI-19 | NFR-I18N-001, NFR-RESP-001 | Sweep labels/errors/aria, typography, mobile/tablet and theme. | Test | UI-08–17 | catalog/pages/styles, `12-design-route-map.md` | i18n/terminology/a11y/visual | in_progress |
| UI-20 | NFR-COMPAT-001, NFR-MAINT-001 | Remove only proven-dead CSS/components and update compatibility docs. | Cleanup | UI-18/UI-19 | globals/styles/legacy docs | import/build/visual evidence | pending |
| UI-21 | all | Independent architecture/UX/a11y/regression/medical-safety review and repairs. | Root + reviewers | UI-20 | changed files | final review loop | pending |
| UI-22 | all | Final reports, commits, push/PR and controlled deploy if approved by evidence. | Root | UI-21 | docs, git, deploy | full release checklist | pending |
| UI-23 | FR-OVR-001, NFR-A11Y-001, NFR-RESP-001, NFR-SEC-001 | Rebuild the professional Dashboard from the supplied reference with real data, scoped wording and correct alert routing. | Root | UI-05/UI-06/UI-18 | dashboard page, system normalizer, Icon, tests/evidence | unit + four-viewport E2E + build | done |

## Traceability matrix

| Requirement groups | Tasks | Implementation files | Tests/evidence | Status |
|---|---|---|---|---|
| FR-NAV / FR-SHELL | UI-05–07 | navigation registries, AppShell, navigation components | workspace, route, shell, mobile E2E | done |
| FR-OVR / FR-TODAY | UI-08/UI-23 | dashboard/today, system normalizer, LifeMap Today projection | state + structured-alert/API contract tests + four-viewport E2E + screenshots | done |
| FR-LIFE | UI-09 | lifemap/guided-flow | wizard/safety/E2E | pending |
| FR-VISIT | UI-10 | visits/new/flow | integration/E2E | done |
| FR-FAM | UI-11 | family pages/components | tab/invite/revoke/E2E | done |
| FR-PHR | UI-03/UI-12 | icon, PHR routes/components, observations API | icon/form/provenance/API/E2E | done |
| FR-MED | UI-13 | medicines components | normalization/DDI/flow tests | done |
| FR-CHAT / FR-EVID / FR-RES | UI-14–15 | Chat V2, Evidence, Source Hub | citation/privacy/role/E2E | in_progress |
| FR-COUNCIL | UI-16 | Council routes/view models | safety/role/E2E | in_progress |
| FR-SCRIBE | UI-17 | Scribe routes/components/libs | workflow/consent/sign tests | in_progress |
| NFR-A11Y | UI-04/UI-18/UI-19 | primitives, e2e config | axe/manual/focus/target/reflow | in_progress |
| NFR-PERF | UI-18/UI-20 | bundle script, lazy boundaries, CSS | budget/hydration/visual | in_progress |
| NFR-THEME/I18N/RESP | UI-02/UI-19 | tokens/catalog/pages | token/i18n/terminology/screenshots | in_progress |
| NFR-SEC/SAFE/PRIV/AUDIT | UI-08–17, UI-21 | UI only; server contracts preserved | API safety suites + UI regression | pending |
| NFR-COMPAT/MAINT | UI-01/UI-05/UI-20 | registries, aliases, CSS/docs | route/build/import/architecture review | pending |
