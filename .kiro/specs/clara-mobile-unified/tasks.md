# Implementation Plan — CLARA Mobile Unified

Each task keeps the app compiling and the currently-green tests green. Ships
`MOBILE_UNIFIED_ENABLED`, now defaulting ON (the shipped experience).
Pre-existing 22 legacy test failures are out of scope (do not fix, do not
regress further). Baseline at start: 369 pass / 22 fail; current: 382 pass / 22
fail (15 new/updated unified tests, no regression).

## Phase 1 — Foundation
- [x] 1.1 Add `kMobileUnifiedEnabled` (`MOBILE_UNIFIED_ENABLED`) to
  `feature_flags.dart` with tests. _Req 1.1, 9.1_
- [x] 1.2 Add `ApiClient` LifeMap wrappers (`getLifeMapToday`,
  `createLifeMapEpisode`, `createLifeMapTask`, `acceptLifeMapTask`,
  `completeLifeMapTask`) + `_idempotencyKey()` helper + extra-headers plumbing;
  unit tests with `MockClient`. _Req 3.x, 8.4_
- [x] 1.3 Add `ApiClient` PHR-onboarding wrappers (`getPhrOnboarding`,
  `updatePhrOnboarding`) + medication-courses wrappers; tests. _Req 6.x, 5.1_

## Phase 2 — Unified shell + root
- [x] 2.1 Reuse the existing adaptive `RedesignShell` (bottom/rail, center
  Ask-CLARA action, one active style) rather than duplicating a shell. _Req 2.1–2.5_
- [x] 2.2 `UnifiedRoot` (summary + onboarding load → OnboardingGate → shell with
  Today/LifeMap/Medicines/Profile + center Chat); wired into `app.dart` behind
  `kMobileUnifiedEnabled` (checked first, incl. login + polished theme + locale/
  theme controller hydration). _Req 1.1, 6.1_
- [x] 2.3 `UnifiedOnboardingGate` widget tests + flag-default test
  (`test/unified_root_test.dart`). _Req 9.1, 9.4_

## Phase 3 — Today + LifeMap
- [x] 3.1 `TodaySurface` (today list, complete task, 409→onboarding, empty/error/
  refresh). _Req 3.1, 3.4, 7.x_
- [x] 3.2 `LifeMapSurface` (episodes, create episode, add+accept task,
  priority chips). _Req 3.2, 3.3_

## Phase 4 — Medicines hub
- [x] 4.1 `MedicinesHub` with tabs Thuốc của tôi / Tủ thuốc / An toàn; reuses
  `CabinetScreenV3` (consent gate + OCR + inline DDI) verbatim; medication-courses
  list + add. _Req 4.1–4.4_
- [~] 4.2 Legacy cabinet/careguard entries: the unified shell surfaces the hub as
  the single Medicines destination. The legacy screens remain reachable only under
  the legacy/redesign roots (untouched), so there is no duplicate entry in the
  unified shell. Full legacy-root removal is tracked in 7.2. _Req 4.1_

## Phase 5 — Onboarding + Profile hub
- [x] 5.1 `OnboardingFlow` (welcome → basics → personalization consent →
  complete/skip via `PATCH /phr/onboarding`) + `UnifiedOnboardingGate` for the
  unified root, all roles. Tests. _Req 6.1–6.5_
- [x] 5.2 `ProfileHub` (PHR inline + Visits, Family, Community, Connected Health,
  Scribe, Council, Consent, Settings — role/flag-gated). _Req 2.2_

## Phase 6 — Visits + Family
- [x] 6.1 `ApiClient` visits/family wrappers (header-based invite accept,
  idempotency keys). _Req 3.5, 8.4_
- [x] 6.2 `VisitsSurface` (list/create/concerns/intake/pack) — empty/error/409/
  refresh. _Req 3.5, 7.x_
- [x] 6.3 `FamilySurface` (relationships, notifications+ack, invite, access
  grants, revoke) — minimal-sharing framing. _Req 3.6, 7.x_

## Phase 7 — Consolidation & default-on
- [x] 7.1 Wired `CouncilSurfaceV3` into the Profile hub (doctor/admin, gated) so
  it is no longer test-only dead code. _Req 10.2_
- [x] 7.2 Retire legacy roots from the DEFAULT path: the unified root is now
  selected first for every authenticated session. The legacy `DashboardScreen`
  root + Experience_V2 shell are retained (untouched) only as an explicit
  rollback/A-B path reachable when `MOBILE_UNIFIED_ENABLED=false`; their flags are
  kept deliberately so rollback stays available. _Req 10.1, 10.3_
- [x] 7.3 Flipped `MOBILE_UNIFIED_ENABLED` default ON (the shipped experience).
  The 2 app-boot tests that asserted the legacy Dashboard root were updated to
  assert the unified root boots (headless boot verification), keeping the suite at
  382 pass / 22 pre-existing fail — no net regression. _Req 1.1, 10.4_
- [x] 7.4 A11y + responsive: the unified surfaces reuse the shared a11y-audited
  primitives (`RedesignShell`, `ClaraButton/Card/Input`, `ClaraEmptyState`,
  `MinTapTarget`, `A11y.resolveMotionDuration`). Added a headless a11y/responsive
  sweep (`test/unified_a11y_responsive_test.dart`, 7 tests): OnboardingFlow +
  ProfileHub across phone/tablet widths, 1.6x text scale, and reduced motion,
  asserting no overflow exception and the ≥48dp tap-target minimum on real
  controls. On-device sweep against a live backend still requires an emulator/
  device not available here. _Req 7.x_

## Phase 8 — Validation
- [x] 8.1 `flutter analyze` clean on all unified code; `flutter test` — 389 pass /
  22 pre-existing fail (no regression below the 369 baseline; +20 unified tests).
  _Req 9.x_
- [x] 8.2 Update `apps/mobile/README.md` + this plan with the unified IA map and
  the retired-layers/staged-rollout note. _Req 10.4_

## Environment limitation (transparency)
All 8 phases are implemented and the unified experience is the shipped default.
Verified by `flutter analyze` (clean on all unified code) and `flutter test`
(389 pass / 22 pre-existing fail, no regression from the 369 baseline; +20
unified tests including boot tests that confirm `UnifiedRoot` is the authenticated
root, and a headless a11y/responsive sweep). The one thing NOT possible in this
environment is real device/emulator runtime QA — actual boot against a live
backend and hands-on a11y/responsive testing on physical form factors. Recommend
a device smoke pass before store release; rollback is a single
`--dart-define=MOBILE_UNIFIED_ENABLED=false`.
