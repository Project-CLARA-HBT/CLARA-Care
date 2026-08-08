# UI modernization test plan

## Test principles

Tests prove behavior, not only compilation or source strings. Safety and API authorization remain server-authoritative. UI fixtures use synthetic profiles and no real health data. Each milestone runs the closest tests first, repairs failures, then runs the relevant full suite.

## Commands

```bash
cd apps/web
npm ci
npm run consumer-terminology:check
npm run i18n:check
npm run route-matrix:check
npm run lint
npm run type-check
npm run test:unit
npm run build
npm run bundle:check
npm run test:e2e
npm run test:a11y
npm run test:e2e:visual
```

Repository gates remain relevant:

```bash
make lint
make type-check
make test
```

Run API/ML safety/contract suites for changed client contracts; no UI test replaces them.

## Unit/component matrix

| Area | Tests |
|---|---|
| Route/access/workspace | role × flag availability, max 7, More reachability, canonical workspace, aliases, forbidden state |
| Icon | typed map, fallback, decorative/meaningful semantics, PHR names absent |
| Field/Alert | labels, required/optional, hint/error association, `aria-invalid`, one live announcement |
| SideSheet/Modal/Confirm | initial focus, trap, Escape, inert background, restore focus, async rerender |
| Sidebar/Profile/More | active state, collapse persistence, one CTA/profile, keyboard menu |
| Today | loading/empty/error/data/pending confirmation; no fabricated metrics |
| LifeMap | step guards, draft resume, review/commit, no add-task before episode, truth-state view model |
| Visits | five step transitions, dirty/back/refresh, candidate confirmation, share review |
| Family | tabs, independent async states, expiry/revoke/audit, token exclusion |
| PHR | progress states, focused section, provenance, conflict handling, icon regression |
| Medicines | normalization clarification, confirmed/unconfirmed, one Add CTA, DrugBank unavailable |
| Chat/Evidence | two-column model, answer ordering, canonical citations, role disclosures, explicit evidence confirm |
| Council/Scribe | case context, escalation-first, consent, stage transitions, finalized vs signed, audit locks |

## Integration/contract tests

- Guided-flow draft create/update/resume/commit and revision conflict.
- Visit create → concerns → documents → questions → review → pack/share.
- Family invitation preview/accept/revoke/expiry.
- PHR section save with current full-record contract; conflict must not silently overwrite.
- Medicines normalize → confirm → DDI result or safe unavailable.
- Scribe consent → recording/transcript/SOAP/sign and recording-derived deletion boundaries.
- Council role/ownership, evidence opaque IDs, handoff/oversight reason and audit response.
- Profile isolation and route access for every API call.

## E2E fixture and scenarios

Create a typed fixture factory instead of the current catch-all 200 response. UI-bypass fixtures are explicitly not authorization proof; add a separate real-auth/API contract project for RBAC and consent:

```text
e2e/fixtures/session.ts       normal/researcher/doctor/admin
e2e/fixtures/personal.ts      Today/LifeMap/Visit/Family/PHR/Medicines
e2e/fixtures/research.ts      Chat/Evidence/Sources
e2e/fixtures/clinical.ts      Council/Scribe
```

Split specs:

1. `public.spec.ts`: landing/auth/legal/public-share shell boundaries.
2. `shell-workspaces.spec.ts`: role matrix, workspace switch, More, collapse, direct/forbidden routes.
3. `personal-flows.spec.ts`: Today, LifeMap, Visit, Family, PHR, Medicines.
4. `chat-research.spec.ts`: history drawer, answer/source disclosure, Evidence.
5. `clinical.spec.ts`: Council/Scribe clinician flow.
6. `accessibility.spec.ts`: axe and manual-assisted checks.
7. `visual.spec.ts`: fixed synthetic states and screenshots.
8. `compatibility.spec.ts`: all legacy redirects and flags.

Use four projects: 1440×900, 1280×800, 768×1024, 390×844. Fix timezone, locale, clock, reduced motion, dynamic data masking, and worker count 1.

E2E fails on `pageerror`, unexpected `console.error`, hydration warnings, horizontal overflow, wrong final URL, and missing main landmark. Broad API mocks are not authorization proof; pair with API contract tests.

The trust-boundary contract test changes local role/workspace to `admin` while the server session remains `normal`, and tests the inverse stale-role case. It asserts protected API 403/unauthorized state and absence of admin telemetry. API tests cover normal/researcher/doctor/admin/unknown projections; unknown role fails closed. Public share routes are asserted shell-free, analytics-free, and safe for invalid/expired/revoked tokens.

## Accessibility matrix

- Add `@axe-core/playwright`; run representative routes in light/dark and mobile.
- Keyboard-only: skip link, shell, More, tabs, stepper, dialogs, drawers, forms, source disclosures.
- Focus: initial/return focus and inert background for every overlay.
- Semantics: headings, landmarks, active nav, labels, error summaries, live statuses, table/list semantics.
- Visual: contrast, non-color state, forced colors, reduced motion, 200% zoom, 320px reflow, target size.
- Vietnamese: diacritics, screen-reader labels, translated errors/loading/empty/aria labels.

## Visual and performance evidence

Baseline files are under `docs/ui-modernization/evidence/baseline/`. After implementation capture the same synthetic pages at all required viewports and light/dark where meaningful. Review diffs; never blindly update snapshots.

Bundle check reads clean `next build` manifests. Initial budget is baseline plus 5% per common/per-route artifact; explain exceptions. Preserve lazy Mermaid, export, admin telemetry, and history chunks. Record hydration warnings, console errors, obvious layout shifts, and route transition behavior.

Add explicit hostile fixtures for emergency fast-path, CRITICAL FIDES block, DrugBank unavailable, no-CoT/uncalibrated confidence, and Scribe consent/finalized-vs-signed failures. Assert the safety banner/action is visible before any disclosure. No test is allowed to treat hidden React content as safe if the sensitive payload reached a non-authorized browser.

## Safety/privacy regression matrix

- Emergency text remains first response and escalation visible.
- Consent required before health/recording mutation.
- RBAC and profile isolation remain server-backed.
- DrugBank unavailable is not all-clear; no LLM identity/DDI substitution.
- LifeMap AI cannot confirm truth-state.
- FIDES/claim/citation gates remain visible and authoritative.
- No CoT, raw prompt, uncalibrated confidence, provider secrets, or PII in DOM/telemetry/fixtures.
- Scribe no auto-R69/confidence; signed note and audit remain controlled.

Consumer terminology scan covers visible text, labels, loading/error/empty states and aria attributes; the allowlist is limited to expert/admin surfaces and canonical safe copy.

## Manual checklist and reporting

For each milestone record command, timestamp, pass/fail/not-run, failure evidence, repair commit, and rerun. A skipped dependency is “not run” with exact reason, never “pass.”

Current commands are executable: `npm run lint`, `npm run type-check`, `npm run test:unit`, `npm run build`, `npm run test:e2e`, `npm run test:a11y`, `npm run test:e2e:visual`, `npm run bundle:check`, `npm run route-matrix:check`, `npm run i18n:check`. A11y/visual smoke runs against the standalone artifact; the full E2E project still includes the documented legacy shell assertion failures from baseline until its assertions are repaired.
