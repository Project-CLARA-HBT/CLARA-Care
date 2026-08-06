# Decisions and progress log

## Decisions

| Date | Decision | Reason / alternatives |
|---|---|---|
| 2026-08-06 | Preserve every capability through workspace More/context/direct links. | User previously rejected simplification that made the navbar look empty; hiding routes is not acceptable. |
| 2026-08-06 | Separate route access from navigation presentation. | Current coupling can turn a menu cleanup into an authorization regression. |
| 2026-08-06 | Do not invent patient directory or Admin Settings. | Source/backend does not provide those capabilities; labels must not imply features. |
| 2026-08-06 | Keep medication course, cabinet, and PHR models distinct. | Names alone cannot prove identity/provenance. |
| 2026-08-06 | Use typed bundled SVG icons with fallback. | Rounded Material Symbols is unloaded and external fonts are a resilience/privacy risk. |
| 2026-08-06 | Keep Chat rollback and legacy CSS until parity evidence. | Compatibility is a release safety requirement. |
| 2026-08-06 | Keep warnings/escalation visible; collapse only technical detail. | Progressive disclosure cannot hide medical safety information. |
| 2026-08-06 | No DB migration for core presentation milestones. | Existing contracts can support honest UI states; optional schema improvements need separate rollback. |
| 2026-08-06 | Treat `/dashboard` as a professional, role-aware workspace rather than a personal LifeMap home. | Route policy allows researcher/doctor/admin only; personal users already land on `/today`. The supplied mock informs hierarchy and visual language, not authorization or fabricated personal data. |
| 2026-08-06 | Preserve structured dashboard alerts through the web normalizer. | Flattening alert objects lost severity and destination, which could hide a critical warning or send the user to the wrong workflow. |
| 2026-08-06 | Never infer health stability from an empty operational alert list. | The dashboard now says only whether CLARA flagged work in the loaded scope and displays an explicit unknown state while loading or after failure. |
| 2026-08-06 | Use the supplied Clara Health System palette as the exact dark-mode token source. | It replaces the old charcoal override globally while preserving approved light-mode behavior and contrast guards. |
| 2026-08-06 | Represent blocked evidence release as insufficient evidence, not a partial clinical conclusion. | The UI offers only evidence refinement already present in Chat and the existing visit-preparation route; it does not imply clinician availability. |

## Audit feedback resolution

- Architecture audit: Critical workspace/access coupling and AppShell responsibility accepted as M2 priorities.
- Product/IA audit: Personal/Clinical/Research/Admin matrix accepted; direct links/More preserve access; “Bệnh nhân” rejected without backend capability.
- Design/a11y audit: raw icon bug, SideSheet focus, token cleanup, touch targets, live regions accepted as M1.
- Chat/Research audit: two-column answer-first disclosure and one canonical source list accepted as M4.
- Personal flows audit: honest dashboard, focused LifeMap/Visit/Family/PHR/Medicines flows accepted as M3; model merges rejected.
- Clinical/Scribe audit: canonical stage and finalized-vs-signed distinction accepted as M5; server contract remains authoritative.
- Testing/performance audit: typed fixtures, four viewports, axe, bundle budget, console/hydration checks accepted as M7.
- Planning review resolutions: Clinical primary routes use only existing `/dashboard`, `/chat`, `/council`, and `/scribe`; `/phr` is contextual and profile-kind labelled. The exhaustive route manifest is a pre-M2 gate. LifeMap/Visit/PHR contracts are conditional and must not be presented as saved when unsupported. More is labelled and ≤2 interactions. UI-bypass E2E is separated from real auth/RBAC/consent contract tests. Emergency/FIDES/DrugBank/no-CoT/Scribe and public-share shell boundaries are explicit test gates. Initial rollback is milestone revert; no shell flag is claimed before implementation.

## Progress

### Baseline (2026-08-06)

- Branch created: `feat/ui-modernization-v2`.
- Pre-existing user-owned changes preserved and not staged: `scripts/deploy/redeploy_app_stack.sh`, `CLARA_CODEX_MASTER_IMPLEMENTATION_SPEC.md`, `chathistory.md`, two demo JSON files.
- `npm run lint`: pass with eight pre-existing React Hook warnings.
- `npx tsc --noEmit`: pass.
- Vitest: 87 files / 677 tests pass.
- `npm run build`: pass; 91 routes generated; 104 kB shared first-load JS.
- Synthetic screenshots captured in `evidence/baseline/` for public landing/login and personal/clinical representative routes at desktop/mobile.
- Task screenshots were not available in the environment; this is documented in the current-state audit.

### Current gate

- Specification documents 00–11: created.
- Planning reviews: complete; three independent reviews were received and their resolutions are recorded above.
- `PLANNING_GATE`: passed on 2026-08-06 after route-matrix and bundle checks plus desktop/mobile accessibility and visual smoke passed against the standalone production artifact.
- Baseline E2E: `npm run test:e2e` on 2026-08-06, 6 passed / 2 failed / 2 skipped in 2m3s; failures are stale shell assertions and remain tracked for repair.

### Implementation checkpoints (2026-08-06)

- M1 foundation: typed SVG Icon/fallback and PHR icon migration. Targeted Vitest 5/5 and type-check pass. No API/schema changes.
- M2 shell: route access split from presentation, four workspaces, ≤7 primary items, More/context routes, profile/logout consolidation, mobile focus trap/restore. Navigation/unit tests pass; route matrix remains 79/79.
- M3 personal: Today no longer fabricates fallback cards/metrics; Family uses URL-backed Shared/Received/Access Log tabs; Visit preparation uses URL-backed four-step disclosure; Dashboard unknown states replace fabricated activity/council/confidence values. Personal presentation regression tests pass.
- M4 Chat: answer renders before collapsed explainability details; researcher/admin integrity diagnostics are collapsed and normal users do not receive them; browser-side hidden-reasoning/raw-confidence line filter added. Chat canvas tests 16/16 pass.
- M5 clinical: Scribe uses shared calm surfaces and explicit Record → Transcript review → SOAP review → Complete stepper; Council receives catalog-backed page heading. Existing Scribe safety/integration tests pass.
- M7 harness: `route-matrix:check`, `bundle:check`, i18n, type-check, desktop/mobile axe and visual smoke pass against standalone artifact. Full unit suite: 91 files / 694 tests passed after the post-review consent and answer-boundary coverage. Full E2E: 27 passed, 5 failed (shell assertions/temporary mobile proxy error under repair), 4 skipped.
- Post-review safety repairs: Scribe now requires an explicit consent checkbox and consent API capture before `getUserMedia`; completion is labeled as a draft rather than a signed/exported note. The answer boundary now filters common English/Vietnamese/XML reasoning markers. Mobile drawer initial focus excludes the backdrop and route navigation restores focus to its trigger. Dashboard no longer maps global runtime request totals to personal case counts.
- Dashboard visual follow-up: rebuilt from the provided reference using existing semantic tokens and typed SVG icons; kept the real professional route/RBAC contract; introduced researcher/doctor/admin shortcut sets; retained structured alert severity/message/href; removed medical reassurance from unknown/empty operational states; used `--text-brand` for dark-mode AA contrast; and added dashboard E2E at all four supported viewports. Independent review findings were repaired before deployment.
- Dashboard release: checkpoint `316a9599` pushed and deployed to `theclaracare.com`. VPS backup `/opt/clara-backups/pre-dashboard-20260806-135130.tgz`; fresh Node 20 image built successfully; unauthenticated `/dashboard` follows the intended login redirect; live mobile browser smoke has no page/5xx errors and security headers remain present.
- Today real-data follow-up: `/lifemap/today` now returns a read-only, timezone-aware seven-day completion projection plus the scoped task's episode title/version. `/today` selects active, completed, caught-up, or first-time presentation from those values only. It never auto-completes a task or turns a pending draft into a conclusion. `completeLifeMapTask` sends `If-Match` when the server supplied a version. After E2E found a real 22–23px tablet/mobile overflow caused by raw icon-font fallback text, the mobile notification and More icons moved to the bundled SVG abstraction; four-viewport Today E2E is now 12/12. Checkpoint `082cd3cc` was pushed and deployed on 2026-08-06: VPS backup `/opt/clara-backups/pre-today-20260806-143635.tgz`, API readiness is `ready`, and unauthenticated `/today` correctly redirects to login with security headers intact. No migration was required.

### Checkpoint template

```text
Checkpoint:
Commit:
Scope/files:
Requirements/tasks:
Tests run:
Pass/fail/not-run evidence:
Safety/privacy review:
Rollback target:
Open follow-up:
```

## Rejected or deferred items

- New patient directory and Admin Settings route: rejected as non-functional invention.
- PHR PATCH/ETag, recurring reminders, and server-resumable Visit fields: deferred optional API work; UI must fail honestly until available.
- Full mobile Flutter redesign: out of scope; terminology synchronization remains required.
- Bulk deletion of legacy CSS/Chat: deferred until import/flag/visual evidence.
