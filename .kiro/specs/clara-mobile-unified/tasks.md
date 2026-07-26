# Implementation Plan — CLARA Mobile Unified

Each task keeps the app compiling and the 369 currently-green tests green. Ships
behind `MOBILE_UNIFIED_ENABLED` (default OFF) until Phase 7. Pre-existing 22
legacy test failures are out of scope (do not fix, do not regress further).

## Phase 1 — Foundation
- [ ] 1.1 Add `kMobileUnifiedEnabled` (`MOBILE_UNIFIED_ENABLED`, default false) to
  `feature_flags.dart` with tests. _Req 1.1, 9.1_
- [ ] 1.2 Add `ApiClient` LifeMap wrappers (`getLifeMapToday`, `createEpisode`,
  `createEpisodeTask`, `acceptTask`, `completeTask`) + `_idempotencyKey()` helper;
  unit tests with `FakeApiClient`/mock transport. _Req 3.x, 8.4_
- [ ] 1.3 Add `ApiClient` PHR-onboarding wrappers (`getPhrOnboarding`,
  `updatePhrOnboarding`) + medication-courses wrappers; tests. _Req 6.x, 5.1_

## Phase 2 — Unified shell + root
- [ ] 2.1 `UnifiedDestination` model + role-aware list; `UnifiedShell` (adaptive
  bottom/rail, center Ask-CLARA action, one active style). _Req 2.1–2.5_
- [ ] 2.2 `UnifiedRoot` (Login → ConsentGate → OnboardingGate → UnifiedShell);
  wire into `app.dart` behind `kMobileUnifiedEnabled` (checked first). _Req 1.1, 6.1_
- [ ] 2.3 Shell + root widget tests (destinations, role gating, flag-off
  equivalence). _Req 9.1, 9.4_

## Phase 3 — Today + LifeMap
- [ ] 3.1 `TodaySurface` (today list, complete task, 409→onboarding, empty/error/
  offline). Tests. _Req 3.1, 3.4, 7.x_
- [ ] 3.2 `LifeMapSurface` (episodes, create episode, add+accept task, optional
  next-question). Tests. _Req 3.2, 3.3_

## Phase 4 — Medicines hub
- [ ] 4.1 `MedicinesHub` with tabs List / Cabinet / Safety; reuse cabinet + DDI
  logic; preserve consent gate + disclaimers + low-confidence confirm. Tests.
  _Req 4.1–4.4_
- [ ] 4.2 Route the legacy cabinet/careguard entries through the hub; remove
  duplicate shell entries. _Req 4.1_

## Phase 5 — Onboarding + Profile hub
- [ ] 5.1 `OnboardingFlow` (welcome → basics → personalization consent →
  complete/skip via `PATCH /phr/onboarding`) + `OnboardingGate` for the unified
  root, all roles. Tests. _Req 6.1–6.5_
- [ ] 5.2 `ProfileSurface` hub (PHR, Visits, Family, Connected Health, Consent,
  Evidence, Settings, Guide — role-aware). Tests. _Req 2.2_

## Phase 6 — Visits + Family
- [ ] 6.1 `ApiClient` visits/family/care-tasks wrappers (header-based invite
  accept) + tests. _Req 3.5, 8.4_
- [ ] 6.2 `VisitsSurface` (list/create/concerns/intake/plan/pack) — empty/error/
  offline. Tests. _Req 3.5, 7.x_
- [ ] 6.3 `FamilySurface` (relationships, notifications+ack, invite, access
  grants/log, revoke) — minimal-sharing framing. Tests. _Req 3.6, 7.x_

## Phase 7 — Consolidation & default-on
- [ ] 7.1 Wire `CouncilSurfaceV3` into the shell or delete it (no test-only dead
  code). _Req 10.2_
- [ ] 7.2 Retire legacy `DashboardScreen` root + Experience_V2 shell from the
  authenticated path; keep reused screens; remove now-dead flags/roots. _Req 10.1,
  10.3_
- [ ] 7.3 Flip `MOBILE_UNIFIED_ENABLED` default ON; update flag docs + README.
  _Req 1.1, 10.4_
- [ ] 7.4 A11y + responsive sweep (phone/tablet, text scale, reduced motion,
  tap targets) across unified surfaces. _Req 7.x_

## Phase 8 — Validation
- [ ] 8.1 `flutter analyze` clean on unified code; `flutter test` — no regression
  below the 369 green baseline; add unified-surface coverage. _Req 9.x_
- [ ] 8.2 Update `apps/mobile/README.md` + design docs with the unified IA map and
  the retired-layers note. _Req 10.4_
