# CLARA UI Modernization — Implementation Report

## Executive summary

The web application now has a documented, workspace-based navigation model, a task-first shell, typed SVG icons, progressive disclosure for personal flows, safer Chat presentation, and a calmer Scribe workflow. Existing routes remain reachable through primary navigation, More/context actions, direct links, and compatibility redirects; server-side authorization remains authoritative.

## Delivered

- Planning gate and full UI modernization specification in `docs/ui-modernization/00...11`.
- Personal, clinical, research, and admin workspace navigation with a seven-item primary limit.
- AppShell focus trap/restore, mobile drawer, workspace switcher, profile selector, and consolidated profile/logout controls.
- PHR SVG icon abstraction and Button icon fallback; no raw icon names in the PHR hub.
- Today, Family, Visit preparation, Chat, Dashboard, Council, and Scribe presentation improvements.
- Scribe consent-before-microphone gate and draft-versus-signed wording.
- Answer sanitization for telemetry and common hidden-reasoning markers.
- Route capability matrix, i18n contract checks, bundle budget check, axe smoke, visual smoke, and four viewport Playwright projects.

## Validation

- `npm run type-check`: pass.
- `npm run i18n:check`: pass (3,271 Vietnamese/English keys; 38 migrated surfaces).
- `npm run lint`: pass with eight pre-existing React Hook warnings.
- `npm run test:unit`: pass, 91 files / 695 tests.
- `npm run build`: pass, 91 app routes.
- `npm run route-matrix:check`: pass, 79/79 page routes.
- `npm run bundle:check`: pass within the measured 5% budget.
- Full Playwright E2E across desktop, laptop, tablet, and mobile: 31 passed, 5 intentionally skipped by viewport applicability.
- Axe and visual smoke: pass for `/` and `/login` across all four viewports.

## Safety and privacy

No medical decision logic, RBAC, consent backend, audit, emergency, DrugBank, FIDES, or provenance contract was weakened. The browser Scribe flow now requires explicit consent capture before microphone access. Raw chain-of-thought, provider diagnostics, and uncalibrated confidence are not shown to ordinary users.

## Known limitations

- Dashboard still contains legacy Vietnamese copy and should receive a dedicated typed catalog migration.
- Some legacy Material Symbols usage remains outside the PHR/Button boundary.
- The public landing no longer calls authenticated consent APIs; the former mobile proxy 500 is regression-tested and resolved.
- Authenticated real-user RBAC/consent E2E requires service credentials and was not fabricated in this environment.

## Rollback

Revert commit `05ef3751` or deploy the previous known-good web artifact. No database migration was introduced. The uncommitted deployment-script change and unrelated user data remain untouched.

## Branch / review

Branch: `feat/ui-modernization-v2`  
Pull request: https://github.com/Project-CLARA-HBT/CLARA-Care/pull/117

## Production deployment

- Deployed commit: `f360e7b9`.
- Target: `https://theclaracare.com` (`36.50.27.240`).
- Web image rebuilt without cache on Node `v20.20.2` and the web container was force-recreated only after the image build passed.
- Live verification: `/`, `/login`, `/share/not-a-real-token`, and `/phr/shared/not-a-real-token` return `200`; a mobile Playwright load of `/` reports no 5xx response or page error.
- Security headers verified live: CSP, HSTS, `nosniff`, `DENY` frame policy, strict referrer policy, and permissions policy.
- Rollback backup: `/opt/clara-backups/pre-ui-20260806-090113.tgz`.
- `/.well-known/assetlinks.json` remains intentionally fail-closed (`404`) because the production Android release certificate fingerprint is not configured and no release keystore is present on the server. Do not invent or substitute a debug fingerprint; set `ANDROID_APP_LINK_CERT_SHA256` after the release certificate exists, then recreate the web container.
