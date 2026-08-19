# CLARA Care Product Rebuild — Detailed Task List

**Date:** 2026-08-19  
**Execution style:** dependency-aware, test-first for safety boundaries, vertical slices  
**Legend:** P0 = release gate; P1 = follow-on; P2 = later.  
**Rule:** check a task complete only when code, tests, documentation/telemetry changes and rollback implications for that task are resolved.

---

## EPIC 00 — Baseline, inventory and guardrails

- [ ] **T00-001 [P0] Freeze repository baseline.** Record `main` SHA, relevant feature branch/PR state, build toolchain and production deployment reference in an implementation note. **DoD:** baseline can be reproduced and linked from rebuild PRs.
- [ ] **T00-002 [P0] Generate complete route inventory.** Enumerate all web `page.tsx` routes and Flutter top-level destinations; classify consumer/professional/research/admin/public/compatibility. **DoD:** no unclassified route.
- [ ] **T00-003 [P0] Build legacy-to-canonical route map.** Map `/today`, `/chat`, `/lifemap`, `/phr`, `/medicines`, `/visits`, `/family`, consent routes and all aliases to target disposition. **DoD:** redirect/adaptor tests can be generated from the map.
- [ ] **T00-004 [P0] Freeze safety invariant list.** Include RBAC, profile isolation, consent, GLHS stale commit, emergency path, medication/DrugBank fail-closed behavior, Scribe consent and audit. **DoD:** each invariant links to one or more runnable tests.
- [ ] **T00-005 [P0] Capture current performance baseline.** Record bundle sizes, page build outputs and production/synthetic Core Web Vitals where available. **DoD:** new budgets use real baseline.
- [ ] **T00-006 [P0] Capture current accessibility baseline.** Run axe/keyboard smoke on current primary routes using non-PHI fixtures. **DoD:** known failures categorized as pre-existing vs rebuild regression.
- [ ] **T00-007 [P0] Snapshot current product screenshots.** Desktop/tablet/mobile for landing, Today, Chat, PHR, LifeMap, medication, visit, family, professional pages. **DoD:** no real user data in evidence.
- [ ] **T00-008 [P0] Inventory current API fan-out per key page.** Measure requests made by Today/Home, PHR/Health, Chat and mobile Home. **DoD:** target read models have a quantified reason.
- [ ] **T00-009 [P0] Inventory current feature flags.** Identify flags affecting PHR, LifeMap V2, capture, Chat, Council, Scribe, mobile and model registry. **DoD:** duplicate/obsolete flags marked but not deleted yet.
- [ ] **T00-010 [P0] Define rebuild feature flags.** Add names and owners from TECH_DESIGN without enabling behavior. **DoD:** each major slice can roll back independently.
- [ ] **T00-011 [P0] Define supported browser/device matrix.** Include desktop/laptop/tablet/mobile web and current Android support. **DoD:** E2E matrix documented.
- [ ] **T00-012 [P0] Define analytics privacy policy for rebuild events.** Specify allowed metadata and banned PHI fields. **DoD:** reusable test helper rejects disallowed payload keys.
- [ ] **T00-013 [P0] Create implementation decision log.** Track deviations from package specs. **DoD:** every accepted deviation has rationale, owner and safety impact.
- [ ] **T00-014 [P0] Create rollback checklist.** UI, API, DB migration and model route rollback steps. **DoD:** no phase requires irreversible rollback assumptions.

---

## EPIC 01 — Consumer information architecture and content system

- [ ] **T01-001 [P0] Finalize canonical consumer destinations.** Home, Health, Care, You + Ask action. **DoD:** labels approved VI/EN.
- [ ] **T01-002 [P0] Define professional-mode transition UX.** Personal vs work context for privileged users. **DoD:** ordinary user never sees a workspace switcher.
- [ ] **T01-003 [P0] Create controlled terminology dictionary.** Internal name, VI consumer label, EN consumer label, when technical term may appear. **DoD:** covers PHR, LifeMap, CareGuard, Self-Med, Council, Scribe, evidence, confidence, commit, candidate, pipeline.
- [ ] **T01-004 [P0] Create health-state vocabulary.** confirmed, user-reported, imported, device-sourced, document-extracted, unconfirmed, conflict, stale, stopped/resolved. **DoD:** semantics documented and mapped to API fields.
- [ ] **T01-005 [P0] Create risk/urgency vocabulary.** Ensure consumer words do not overstate diagnostic certainty. **DoD:** deterministic emergency wording cannot be softened by translation.
- [ ] **T01-006 [P0] Define standard answer content order.** Main message -> next actions -> source -> unknowns -> care escalation. **DoD:** implemented as reusable answer renderer contract.
- [ ] **T01-007 [P0] Define error-copy taxonomy.** unavailable, permission lost, sync stale, AI unavailable, state conflict, invalid document, safety block. **DoD:** each has VI/EN message + next action.
- [ ] **T01-008 [P0] Define empty-state taxonomy.** No data vs no tasks vs no results vs unavailable. **DoD:** no empty state implies “healthy/normal” from missing data.
- [ ] **T01-009 [P0] Define notification copy taxonomy.** medication, visit, review, result, safety, sync. **DoD:** severity/action semantics separate from prose.
- [ ] **T01-010 [P0] Migrate new copy to catalog keys.** Establish key naming and typed params. **DoD:** no inline VI/EN branching in new core surfaces except temporary migration adapters.
- [ ] **T01-011 [P1] Build CDC Clear Communication review sheet.** Adapt CCI items to CLARA patient-facing digital surfaces. **DoD:** score calculation and reviewer instructions stored in repo.
- [ ] **T01-012 [P1] Review high-risk copy to CCI >=90.** Emergency, medication interaction, lab explanation, sharing/privacy. **DoD:** score evidence archived.
- [ ] **T01-013 [P0] Add copy semantic-parity tests.** Key presence and urgency/action parity between VI/EN. **DoD:** CI fails on missing critical translations.
- [ ] **T01-014 [P0] Remove “AI engine/cyber system” language from new landing/product copy.** **DoD:** consumer landing focuses on user jobs and trust.
- [ ] **T01-015 [P1] Establish user research script.** Five-second findability, source/uncertainty comprehension, navigation tasks. **DoD:** reusable moderated/unmoderated test plan.

---

## EPIC 02 — Design system and accessibility foundation

- [ ] **T02-001 [P0] Create platform-neutral semantic token source.** Colors, type, spacing, radius, elevation, focus, motion, source states and health statuses. **DoD:** generated web and Flutter outputs match semantic names.
- [ ] **T02-002 [P0] Remove decorative status-color misuse in new components.** **DoD:** red/orange/green reserved for state meaning.
- [ ] **T02-003 [P0] Build consumer typography scale.** Optimized for Vietnamese diacritics and readable health content. **DoD:** responsive size/line-height tokens documented.
- [ ] **T02-004 [P0] Build shared Button/IconButton.** 44px touch-friendly default for primary touch controls. **DoD:** keyboard/focus/disabled/loading variants tested.
- [ ] **T02-005 [P0] Build TextField/TextArea/SearchField primitives.** **DoD:** accessible labels, errors, descriptions and autofill support.
- [ ] **T02-006 [P0] Build Modal/BottomSheet/Drawer primitives.** **DoD:** focus trap/restore, escape/back, screen-reader names, scroll lock.
- [ ] **T02-007 [P0] Build `HealthStateBadge`.** **DoD:** color + text/icon semantics; VI/EN labels.
- [ ] **T02-008 [P0] Build `SourceBadge/SourceDetails`.** **DoD:** source, date, confirmation status accessible without visual clutter.
- [ ] **T02-009 [P0] Build `PrimaryActionCard`.** **DoD:** one dominant action, loading/error variants.
- [ ] **T02-010 [P0] Build `AskBar`.** Text + optional mic/camera/file controls. **DoD:** screen-reader/keyboard/touch parity.
- [ ] **T02-011 [P0] Build reusable Loading/Empty/Error patterns.** **DoD:** no fake data fallback.
- [ ] **T02-012 [P0] Build accessible health chart wrapper.** **DoD:** textual summary and data table/point labels for supported charts.
- [ ] **T02-013 [P0] Add reduced-motion behavior.** **DoD:** all new decorative transitions respect preference.
- [ ] **T02-014 [P0] Add text zoom/scaling test fixtures.** Web 200%; Flutter large accessibility text. **DoD:** critical actions remain usable.
- [ ] **T02-015 [P0] Add focus-not-obscured checks.** Sticky header/bottom nav/composer. **DoD:** keyboard focus always visible.
- [ ] **T02-016 [P0] Add axe smoke for shared primitives.** **DoD:** CI gate.
- [ ] **T02-017 [P1] Review dark theme semantic contrast.** **DoD:** dark mode does not alter urgency meaning.
- [ ] **T02-018 [P0] Remove/retire cyber-grid/glow module styling from new consumer surfaces.** **DoD:** no legacy aesthetic imported into consumer V2.

---

## EPIC 03 — Web shell and navigation architecture

- [ ] **T03-001 [P0] Introduce Next.js route groups for public/consumer/professional/admin.** **DoD:** no route-access behavior changed yet.
- [ ] **T03-002 [P0] Extract `SessionBoundary` from `AppShell`.** **DoD:** 401/session behavior regression tests pass.
- [ ] **T03-003 [P0] Extract `ProfileBoundary`.** **DoD:** profile switch invalidates profile-scoped UI state and tests revoked profile behavior.
- [ ] **T03-004 [P0] Extract preferences provider.** Language/theme/accessibility. **DoD:** no auth coupling.
- [ ] **T03-005 [P0] Replace consumer workspace presentation with consumer nav registry.** **DoD:** Home/Health/Care/You shown; professional navigation hidden in personal mode.
- [ ] **T03-006 [P0] Keep server authorization independent.** **DoD:** direct URL RBAC tests pass even when nav hides link.
- [ ] **T03-007 [P0] Implement desktop consumer navigation.** **DoD:** active state and accessible names tested.
- [ ] **T03-008 [P0] Implement mobile web bottom navigation.** **DoD:** Home/Health/Ask/Care/You and safe-area handling.
- [ ] **T03-009 [P0] Implement active-profile indicator.** **DoD:** profile name/person is visible wherever context can change.
- [ ] **T03-010 [P0] Implement professional-mode entry under You/profile for privileged users.** **DoD:** deliberate transition required.
- [ ] **T03-011 [P0] Implement legacy route redirects behind flag.** **DoD:** route matrix tests.
- [ ] **T03-012 [P0] Add route-group error/loading boundaries.** **DoD:** no provider stack/detail leaks.
- [ ] **T03-013 [P0] Reduce client shell JavaScript.** Move static/layout/server-resolvable concerns out of monolithic client component. **DoD:** bundle delta measured.
- [ ] **T03-014 [P0] Add browser history/deep-link tests.** **DoD:** back/forward/profile switching safe.
- [ ] **T03-015 [P0] Ensure no PHI in URLs.** **DoD:** static/automated scan for medical free-text query params in new routes.

---

## EPIC 04 — Server state and typed API client

- [ ] **T04-001 [P0] Select and configure one server-state query layer for rebuild.** Recommended TanStack Query where interactive client caching is needed. **DoD:** documented cache policy.
- [ ] **T04-002 [P0] Define profile-scoped query-key factory.** **DoD:** profile ID/context version included as required.
- [ ] **T04-003 [P0] Clear/invalidate health queries on profile switch/logout/revocation.** **DoD:** tests demonstrate no stale profile flash.
- [ ] **T04-004 [P0] Create typed `/api/v2` client module.** **DoD:** response validation/error normalization.
- [ ] **T04-005 [P0] Define common API error envelope.** **DoD:** state conflict, unauthorized, feature unavailable, validation and service unavailable mapped to friendly UI.
- [ ] **T04-006 [P0] Define cursor pagination helpers.** **DoD:** timeline/results/documents use common semantics.
- [ ] **T04-007 [P0] Define ETag/base-version client helper.** **DoD:** write requests attach correct precondition.
- [ ] **T04-008 [P0] Define idempotency/command client helper.** **DoD:** safe retry behavior tested.
- [ ] **T04-009 [P0] Prohibit insecure persistent PHI query caching.** **DoD:** audit localStorage/IndexedDB use for new health payloads.
- [ ] **T04-010 [P0] Add request cancellation on route/profile change where appropriate.** **DoD:** stale responses cannot repaint old profile.

---

## EPIC 05 — Home API and consumer Home

- [ ] **T05-001 [P0] Specify `/api/v2/home` schema in code.** **DoD:** OpenAPI/typed client generated or manually typed and tested.
- [ ] **T05-002 [P0] Implement profile-scoped Home service.** **DoD:** server resolves scope; requested profile alone cannot authorize.
- [ ] **T05-003 [P0] Implement top-action prioritizer.** **DoD:** deterministic severity/order rules; no LLM required.
- [ ] **T05-004 [P0] Implement recent-change aggregator.** Results, documents, medication changes, accepted timeline updates, connected measurements. **DoD:** real source IDs only.
- [ ] **T05-005 [P0] Implement Today schedule aggregator.** Accepted tasks, visits, medication reminders where real. **DoD:** no fabricated due dates.
- [ ] **T05-006 [P0] Preserve critical alert severity and target.** **DoD:** regression tests from current dashboard alert behavior.
- [ ] **T05-007 [P0] Add Home cache/outbox invalidation.** **DoD:** accepted write appears without stale long TTL.
- [ ] **T05-008 [P0] Build `/home` web route.** **DoD:** mobile/desktop responsive.
- [ ] **T05-009 [P0] Add prominent Ask bar.** **DoD:** opens/enters Ask with no mode selection.
- [ ] **T05-010 [P0] Build highest-priority action card.** **DoD:** safe severity presentation.
- [ ] **T05-011 [P0] Build recent changes section.** **DoD:** source/type labels and accessible timestamps.
- [ ] **T05-012 [P0] Build Today schedule section.** **DoD:** medication/visit/task items deep-link correctly.
- [ ] **T05-013 [P0] Build calm caught-up state.** **DoD:** no “everything is healthy” implication.
- [ ] **T05-014 [P0] Build Home error state.** **DoD:** “unavailable” cannot become “no alerts”.
- [ ] **T05-015 [P0] Add Home analytics.** Coarse action/event names only. **DoD:** no titles/health values in payload.
- [ ] **T05-016 [P0] Add Home E2E across viewport matrix.** **DoD:** real fixture states active/completed/empty/error/critical alert.
- [ ] **T05-017 [P0] Redirect `/today` to `/home` under migration flag.** **DoD:** old deep links work.

---

## EPIC 06 — Unified Health projection

- [ ] **T06-001 [P0] Define `HealthSummaryV2` schema.** **DoD:** provenance/state fields are mandatory where needed.
- [ ] **T06-002 [P0] Define normalized timeline display event schema.** **DoD:** effective vs recorded time preserved.
- [ ] **T06-003 [P0] Implement Health projection service.** Read PHR/LifeMap/medication/results/measurements/documents without destructive merge. **DoD:** source children retained.
- [ ] **T06-004 [P0] Implement current-state resolver.** **DoD:** corrections/stops/history handled; last mention != current truth.
- [ ] **T06-005 [P0] Implement conflict projection.** **DoD:** unresolved contradictions return review state.
- [ ] **T06-006 [P0] Implement timeline cursor pagination.** **DoD:** stable ordering with equal timestamps.
- [ ] **T06-007 [P0] Implement timeline filters.** medication, symptom/condition, visit, result, measurement, document. **DoD:** server filters, not full-client scan.
- [ ] **T06-008 [P0] Implement source-detail endpoint/view model.** **DoD:** authorized provenance only.
- [ ] **T06-009 [P0] Build `/health` overview.** **DoD:** sections prioritize current important data, not database tables.
- [ ] **T06-010 [P0] Build `/health/timeline`.** **DoD:** period filters, accessible list, source/state badges.
- [ ] **T06-011 [P0] Build timeline detail/revision history.** **DoD:** current view simple; history discoverable.
- [ ] **T06-012 [P1] Add episode grouping.** **DoD:** grouping can be expanded to underlying events.
- [ ] **T06-013 [P1] Add record search.** **DoD:** profile-scoped, no cross-profile cache/search snippets.
- [ ] **T06-014 [P0] Add Health E2E for conflicting/current/historical facts.** **DoD:** exact fixture semantics verified.
- [ ] **T06-015 [P0] Add `/lifemap` and `/phr` migration adapters/redirects.** **DoD:** route parity documented.

---

## EPIC 07 — Bounded PHR/health writes and concurrency

- [ ] **T07-001 [P0] Audit all callers of whole-record `PUT /phr/record`.** **DoD:** web/mobile/other services listed.
- [ ] **T07-002 [P0] Define subresource write endpoints/commands.** demographics, allergies, conditions, medications, emergency/contact data. **DoD:** API contract reviewed for backward compatibility.
- [ ] **T07-003 [P0] Add resource/base version fields.** **DoD:** migration additive and safe.
- [ ] **T07-004 [P0] Implement ETag/precondition enforcement.** **DoD:** stale update rejected.
- [ ] **T07-005 [P0] Implement idempotent create/update commands.** **DoD:** duplicate retry does not duplicate record.
- [ ] **T07-006 [P0] Implement structured conflict response.** **DoD:** current version + changed-field hints without excess PHI.
- [ ] **T07-007 [P0] Build web conflict-reconciliation UI.** **DoD:** local edit preserved.
- [ ] **T07-008 [P0] Migrate new Health editors to bounded writes.** **DoD:** no new screen calls whole-record PUT.
- [ ] **T07-009 [P0] Keep compatibility PUT behind legacy adapter.** **DoD:** old clients remain functional until retirement gate.
- [ ] **T07-010 [P0] Add PostgreSQL concurrent update integration tests.** **DoD:** no silent lost update.
- [ ] **T07-011 [P0] Add consent/authorization TOCTOU tests.** **DoD:** change between read and write causes correct reject.
- [ ] **T07-012 [P0] Add audit reconstruction test for bounded write.** **DoD:** source/user/base version/action recoverable.

---

## EPIC 08 — Medication convergence

- [ ] **T08-001 [P0] Inventory medication representations.** PHR, medication courses, cabinet/CareGuard, OCR candidates, imports. **DoD:** semantic differences documented.
- [ ] **T08-002 [P0] Define consumer medication projection schema.** **DoD:** current state + source children + review state.
- [ ] **T08-003 [P0] Implement normalized identity grouping policy.** **DoD:** low-confidence mappings stay separate/reviewable.
- [ ] **T08-004 [P0] Prevent cabinet scan from implying active use.** **DoD:** regression tests.
- [ ] **T08-005 [P0] Build `/health/medications` list.** **DoD:** one consumer hub.
- [ ] **T08-006 [P0] Build medication detail/history.** **DoD:** start/stop/change timeline visible.
- [ ] **T08-007 [P0] Integrate current authoritative interaction check.** **DoD:** model cannot override DrugBank/approved deterministic result.
- [ ] **T08-008 [P0] Integrate allergy context with unknown-state wording.** **DoD:** missing allergy info is not treated as none.
- [ ] **T08-009 [P0] Add scan medicine entry through Universal Capture.** **DoD:** review before active list inclusion.
- [ ] **T08-010 [P1] Add reminders.** **DoD:** time/recurrence/snooze/pause controls and notification policy.
- [ ] **T08-011 [P1] Add refill/expiry only from real dates/quantities.** **DoD:** no silent estimate.
- [ ] **T08-012 [P1] Add duplicate-therapy review UI.** **DoD:** label as potential review, not prescribing conclusion.
- [ ] **T08-013 [P0] Redirect `/medicines` to canonical medication experience under flag.** **DoD:** query/deep-link compatibility.
- [ ] **T08-014 [P0] Run medication safety regression.** **DoD:** no degraded fail-closed behavior.

---

## EPIC 09 — Labs/results and measurements

- [ ] **T09-001 [P0] Inventory result/lab data sources and units.** **DoD:** source/reference range semantics known.
- [ ] **T09-002 [P0] Define result detail schema.** value, unit, source range, flags, specimen/time, source ID. **DoD:** AI explanation fields separated.
- [ ] **T09-003 [P0] Build `/health/results`.** **DoD:** latest and historical results without fabricated categories.
- [ ] **T09-004 [P0] Build result detail.** **DoD:** exact value/unit/range first.
- [ ] **T09-005 [P0] Implement comparable-trend logic.** **DoD:** unit/method incompatibilities handled.
- [ ] **T09-006 [P0] Build accessible trend chart.** **DoD:** textual equivalent + screen-reader semantics.
- [ ] **T09-007 [P0] Define lab explanation AI task contract.** **DoD:** no invented reference range/diagnosis.
- [ ] **T09-008 [P0] Add numeric fidelity verifier.** **DoD:** answer cannot alter source value/unit/range unnoticed.
- [ ] **T09-009 [P1] Add clinician-question suggestions.** **DoD:** sourced to result/context; user can ignore/edit.
- [ ] **T09-010 [P0] Build measurements view.** **DoD:** source/device and effective time visible.
- [ ] **T09-011 [P1] Add deterministic personal baseline/trend summaries.** **DoD:** missingness and device-change qualification.
- [ ] **T09-012 [P0] Add result explanation evaluation set.** **DoD:** VI/EN, normal/abnormal, missing range, unit edge cases.

---

## EPIC 10 — Model Gateway refactor

- [ ] **T10-001 [P0] Inventory every direct LLM/provider construction path.** **DoD:** no untracked medical model call site.
- [ ] **T10-002 [P0] Introduce `ModelCapability` enum.** text/image/document/structured/tool/long-context as needed. **DoD:** no provider-specific naming.
- [ ] **T10-003 [P0] Introduce route classes.** fast multimodal, quality multimodal, text reasoning, ASR, embedding. **DoD:** current tasks mapped.
- [ ] **T10-004 [P0] Migrate TaskContract from pro/flash profile to route class/capabilities.** **DoD:** manifest remains strict/fail-closed.
- [ ] **T10-005 [P0] Create `ModelProviderAdapter` protocol/interface.** **DoD:** request/response/error normalized.
- [ ] **T10-006 [P0] Wrap existing approved DeepSeek path as adapter.** **DoD:** existing tests/results preserved.
- [ ] **T10-007 [P0] Implement `UnofficialGeminiGatewayAdapter`.** **DoD:** base URL/key server-only; no official API assumptions.
- [ ] **T10-008 [P0] Map `gemini-3.6-flash-high` only through deployment config.** **DoD:** no literal model choice in client request code.
- [ ] **T10-009 [P0] Map `gemini-3.7-tiered` only through deployment config.** **DoD:** same.
- [ ] **T10-010 [P0] Implement synthetic capability probe.** Text + declared image/document + structured output. **DoD:** no PHI used.
- [ ] **T10-011 [P0] Mark failed capability route unavailable.** **DoD:** task resolver fails safely.
- [ ] **T10-012 [P0] Implement normalized timeouts/errors.** **DoD:** provider diagnostics never sent to ordinary user.
- [ ] **T10-013 [P0] Prevent request-owned provider/model.** **DoD:** API validation/security tests.
- [ ] **T10-014 [P0] Add per-task route feature flags.** **DoD:** Gemini can be disabled without UI rollback.
- [ ] **T10-015 [P0] Implement model-run provenance metadata.** **DoD:** task/route/prompt/schema/context digest/latency/safety, no raw PHI analytics.
- [ ] **T10-016 [P0] Ensure truthful retry/fallback provenance.** **DoD:** displayed answer links to actual producing run.
- [ ] **T10-017 [P0] Add gateway contract tests with synthetic fixtures.** **DoD:** adapter behavior reproducible.
- [ ] **T10-018 [P0] Add unexpected version/model drift signal.** **DoD:** gateway-reported identity/config hash change observable.
- [ ] **T10-019 [P0] Document gateway retention/privacy prerequisite.** **DoD:** production PHI use blocked until private gateway handling is known/accepted.
- [ ] **T10-020 [P0] Keep high-risk no-silent-fallback policy.** **DoD:** tests assert errors/approved fallback behavior.

---

## EPIC 11 — Model evaluation and promotion framework

- [ ] **T11-001 [P0] Create `evaluation/product_ai` structure.** **DoD:** per-task manifests/scorers/thresholds.
- [ ] **T11-002 [P0] Freeze general grounded-answer set.** **DoD:** leakage-controlled, versioned.
- [ ] **T11-003 [P0] Freeze personal temporal QA set.** stale/corrected/conflicting/current facts. **DoD:** exact oracles.
- [ ] **T11-004 [P0] Freeze disclosure-safety set.** cross-profile/wrong-purpose/revoked. **DoD:** zero-tolerance categories identified.
- [ ] **T11-005 [P0] Freeze medication wording/tool-faithfulness set.** **DoD:** model cannot contradict authoritative tool.
- [ ] **T11-006 [P0] Freeze document extraction set.** medication/lab/visit docs, quality perturbations. **DoD:** field-level oracle.
- [ ] **T11-007 [P0] Freeze Vietnamese language set.** colloquial, typo, mixed terminology, negation, dates. **DoD:** adjudicated expected behavior.
- [ ] **T11-008 [P0] Add prompt-injection multimodal set.** **DoD:** attempts to change tools/profile/policy fail.
- [ ] **T11-009 [P0] Add structured-output validity metric.** **DoD:** invalid schema rate reported.
- [ ] **T11-010 [P0] Add latency/cost metrics.** **DoD:** p50/p95 and usage where gateway reports it.
- [ ] **T11-011 [P0] Compare existing approved route vs Gemini aliases per task.** **DoD:** promotion report, not blanket winner.
- [ ] **T11-012 [P0] Define promotion thresholds per task.** **DoD:** locked before canary.
- [ ] **T11-013 [P0] Add shadow route execution.** **DoD:** non-authoritative result cannot affect user output/write.
- [ ] **T11-014 [P0] Add canary route selection.** **DoD:** stable cohort, reversible, task-specific.
- [ ] **T11-015 [P0] Add regression gate to CI/release workflow.** **DoD:** approved route cannot regress past threshold silently.
- [ ] **T11-016 [P1] Schedule model drift re-evaluation.** **DoD:** periodic or deployment-triggered automation with no PHI.

---

## EPIC 12 — Consumer Ask rebuild

- [ ] **T12-001 [P0] Define consumer Ask request schema without mode/provider fields.** **DoD:** old research API remains separate/compatible.
- [ ] **T12-002 [P0] Define bounded consumer intent enum.** **DoD:** each intent maps to risk/task contract.
- [ ] **T12-003 [P0] Implement intent planner/router.** **DoD:** unsafe/out-of-scope intent routes to safety path.
- [ ] **T12-004 [P0] Build governed personal-context selector.** **DoD:** profile/purpose/current-state constraints.
- [ ] **T12-005 [P0] Build deterministic evidence table before synthesis.** **DoD:** personal facts have exact IDs/effective times.
- [ ] **T12-006 [P0] Define answer envelope.** main message/actions/sources/unknowns/safety/proposals/disclosure. **DoD:** versioned schema.
- [ ] **T12-007 [P0] Implement personal-claim verifier.** **DoD:** unsupported/stale claims removed or abstain.
- [ ] **T12-008 [P0] Implement external citation verifier.** **DoD:** displayed citation must exist in retrieval result.
- [ ] **T12-009 [P0] Implement context-use disclosure metadata.** **DoD:** UI can say which personal data classes were used.
- [ ] **T12-010 [P0] Build simplified web Ask composer.** **DoD:** no Fast/Deep/Research selector for normal role.
- [ ] **T12-011 [P0] Add camera/file/voice controls conditionally.** **DoD:** platform permission requested on action.
- [ ] **T12-012 [P0] Build answer renderer.** **DoD:** main message first, expandable sources/unknowns.
- [ ] **T12-013 [P0] Build source drawer.** **DoD:** personal vs external sources visually/semantically distinct.
- [ ] **T12-014 [P0] Build “CLARA chưa biết” section.** **DoD:** missing != negative.
- [ ] **T12-015 [P0] Support entry-context Ask from a result/medication/visit/timeline.** **DoD:** scope visible and server validated.
- [ ] **T12-016 [P0] Preserve cancellation and conversation history.** **DoD:** no lost prompt.
- [ ] **T12-017 [P0] Hide advanced research controls from normal users.** **DoD:** role E2E.
- [ ] **T12-018 [P0] Route `/chat` consumer entry to `/ask`.** **DoD:** research/professional advanced mode remains reachable intentionally.
- [ ] **T12-019 [P0] Add Ask accessibility tests.** Composer, stream, sources, stop, attachments. **DoD:** keyboard/screen reader.
- [ ] **T12-020 [P0] Add Ask safety/grounded E2E.** **DoD:** personal context and no-context cases.

---

## EPIC 13 — Universal Capture V2 multimodal

- [ ] **T13-001 [P0] Define supported file/media policy.** MIME, max bytes, max pages, image dimensions, audio limits. **DoD:** server-side enforcement.
- [ ] **T13-002 [P0] Add robust MIME sniffing and filename sanitization.** **DoD:** extension spoof tests.
- [ ] **T13-003 [P0] Preserve malware-scanner fail-closed behavior.** **DoD:** unavailable scanner does not pass artifact through.
- [ ] **T13-004 [P0] Add PDF page rendering/preprocessing.** **DoD:** bounded resources and page count.
- [ ] **T13-005 [P0] Add image orientation/quality metadata.** **DoD:** extraction can flag low-quality source.
- [ ] **T13-006 [P0] Define CaptureCandidate V2 schema.** page/region/span/uncertainty/normalization/review requirement. **DoD:** migration compatible.
- [ ] **T13-007 [P0] Add private multimodal extraction task(s).** **DoD:** task contracts require image/document capability.
- [ ] **T13-008 [P0] Add content-as-data prompt injection guard.** **DoD:** malicious doc cannot modify tools/policy/schema.
- [ ] **T13-009 [P0] Add OCR + VLM disagreement detection.** **DoD:** conflict reason code surfaced.
- [ ] **T13-010 [P0] Add critical-field validators.** medication strength/dose, result value/unit/date, etc. **DoD:** invalid values cannot commit.
- [ ] **T13-011 [P0] Add duplicate/conflict pre-review checks.** **DoD:** candidates flagged, not auto-destroyed.
- [ ] **T13-012 [P0] Build Add entry sheet.** camera, document, medicine, voice, text, manual, connect source. **DoD:** Home/Health launch parity.
- [ ] **T13-013 [P0] Build upload progress/cancel/retry.** **DoD:** no duplicate artifact on retry.
- [ ] **T13-014 [P0] Build page/image preview.** **DoD:** safe access tokens, no public URL leakage.
- [ ] **T13-015 [P0] Build review candidate card.** **DoD:** accept/edit/reject; state/source clear.
- [ ] **T13-016 [P1] Highlight source region/span.** **DoD:** exact page/region for supported extractors.
- [ ] **T13-017 [P0] Ensure extracted candidates remain drafts.** **DoD:** model response cannot directly mark confirmed.
- [ ] **T13-018 [P0] Build GLHS proposal envelope from accepted candidate.** **DoD:** base state/policy/consent/THSS digest included.
- [ ] **T13-019 [P0] Recheck authorization/state atomically at commit.** **DoD:** real DB TOCTOU test.
- [ ] **T13-020 [P0] Preserve original artifact/source after commit according to policy.** **DoD:** provenance view works.
- [ ] **T13-021 [P0] Add manual-entry fallback.** **DoD:** AI outage cannot block add-health-information.
- [ ] **T13-022 [P0] Add multimodal E2E with synthetic artifacts.** **DoD:** image, PDF, failure, conflict, malicious file.

---

## EPIC 14 — Visit preparation and after-visit workflow

- [ ] **T14-001 [P0] Define visit-prep input contract.** Confirmed current facts, recent changes, user goals, upcoming visit metadata. **DoD:** minimum necessary context.
- [ ] **T14-002 [P0] Implement deterministic “changes since” builder.** **DoD:** source revision IDs retained.
- [ ] **T14-003 [P0] Define visit-prep AI task.** **DoD:** questions/summaries cannot invent diagnosis/treatment.
- [ ] **T14-004 [P0] Store summary input digest/version.** **DoD:** stale when source changes.
- [ ] **T14-005 [P0] Build `/care/visits` canonical list.** **DoD:** real upcoming/past data.
- [ ] **T14-006 [P0] Build visit detail.** **DoD:** date/source/instructions and user goals.
- [ ] **T14-007 [P0] Build Prepare with CLARA flow.** **DoD:** user can add/edit own questions.
- [ ] **T14-008 [P0] Build share/export handoff summary.** **DoD:** no hidden reasoning; scope explicit.
- [ ] **T14-009 [P1] Add after-visit document import.** **DoD:** reviewable instructions/tasks/med changes.
- [ ] **T14-010 [P1] Convert accepted follow-up instructions to care tasks.** **DoD:** explicit acceptance and source.
- [ ] **T14-011 [P0] Add stale-summary UI.** **DoD:** recompute offered; old content not presented as current.
- [ ] **T14-012 [P0] Redirect `/visits` to canonical Care route.** **DoD:** deep-link tests.

---

## EPIC 15 — Care navigation

- [ ] **T15-001 [P0] Write intended-use/out-of-scope statement.** **DoD:** reviewed before implementation.
- [ ] **T15-002 [P0] Define deterministic emergency/red-flag rules.** **DoD:** versioned, testable, clinician-reviewed.
- [ ] **T15-003 [P0] Define structured approved question library.** **DoD:** purpose, eligibility, burden, emergency implications.
- [ ] **T15-004 [P0] Implement bounded question selector.** **DoD:** AI cannot ask arbitrary high-risk question outside policy.
- [ ] **T15-005 [P0] Implement acuity/care-setting engine.** **DoD:** outputs bounded classes only.
- [ ] **T15-006 [P0] Implement minimum urgency floor.** **DoD:** generative layer cannot downgrade.
- [ ] **T15-007 [P0] Add wording task for explanation.** **DoD:** cites user-provided drivers, no disease ranking as primary output.
- [ ] **T15-008 [P0] Build `/care/check-symptoms`.** **DoD:** simple stepwise UX, progress, exit, emergency override.
- [ ] **T15-009 [P0] Build urgency result card.** **DoD:** action + when + why; color not sole signal.
- [ ] **T15-010 [P1] Build clinician handoff summary.** **DoD:** structured answers + urgency result, no CoT.
- [ ] **T15-011 [P0] Create adjudicated evaluation set.** **DoD:** under/over-triage scored separately.
- [ ] **T15-012 [P0] Include Vietnamese colloquial/negation/temporal cases.** **DoD:** locked cases.
- [ ] **T15-013 [P0] Include vulnerable/out-of-scope populations.** pregnancy/pediatric etc either validated or explicit safe route-out. **DoD:** no silent generic behavior.
- [ ] **T15-014 [P0] Set hard under-triage release threshold.** **DoD:** locked before canary.
- [ ] **T15-015 [P0] Add adversarial reassurance tests.** **DoD:** user/model cannot talk system below safety floor.

---

## EPIC 16 — Family, sharing and privacy

- [ ] **T16-001 [P0] Define `/you/sharing` read model.** recipients, profile, scopes, purpose, expiry, status. **DoD:** no excess shared content in list.
- [ ] **T16-002 [P0] Build sharing grant wizard.** person -> categories -> purpose/duration -> preview -> confirm. **DoD:** accessible and VI/EN.
- [ ] **T16-003 [P0] Build exact category preview.** **DoD:** user sees what classes are shared before commit.
- [ ] **T16-004 [P0] Build revoke action.** **DoD:** server revocation + UI confirmation.
- [ ] **T16-005 [P0] Test derived/cache invalidation after revoke.** **DoD:** AI summary/share cache cannot remain readable improperly.
- [ ] **T16-006 [P1] Add access-history UI.** **DoD:** only audit facts supported by backend.
- [ ] **T16-007 [P1] Add caregiver digest task.** **DoD:** context filtered before model call.
- [ ] **T16-008 [P0] Build `/you/privacy`.** consent, AI use explanation, export/delete links. **DoD:** plain-language summary before legal detail.
- [ ] **T16-009 [P0] Add AI-use transparency panel.** **DoD:** personal-context usage categories and optional controls accurately described.
- [ ] **T16-010 [P1] Add active sessions/devices UI if backend supports.** **DoD:** revoke semantics tested.
- [ ] **T16-011 [P0] Redirect `/family` and account consent routes.** **DoD:** old links safe.
- [ ] **T16-012 [P0] Cross-profile semantic retrieval test suite.** **DoD:** zero prohibited cross-profile retrieval.

---

## EPIC 17 — Connected Health / Android Health Connect

- [ ] **T17-001 [P1] Audit current Flutter/native plugin capability.** **DoD:** decide existing package vs custom Kotlin bridge.
- [ ] **T17-002 [P1] Define approved initial Health Connect data types.** **DoD:** product/safety rationale per type.
- [ ] **T17-003 [P1] Implement feature availability check.** **DoD:** unsupported devices degrade cleanly.
- [ ] **T17-004 [P1] Implement per-category permission explainer.** **DoD:** permission requested in context.
- [ ] **T17-005 [P1] Implement permission grant/revoke detection.** **DoD:** recheck before sync.
- [ ] **T17-006 [P1] Implement canonical connected-health envelope.** **DoD:** source IDs/time/unit/device metadata preserved.
- [ ] **T17-007 [P1] Implement server connector ingestion endpoint.** **DoD:** idempotent dedupe and profile scope.
- [ ] **T17-008 [P1] Implement steps/activity sync.** **DoD:** checkpoint/retry no duplicates.
- [ ] **T17-009 [P1] Implement sleep sync.** **DoD:** sessions + source identity.
- [ ] **T17-010 [P1] Implement selected vitals sync.** **DoD:** explicit permission and unit normalization.
- [ ] **T17-011 [P1] Implement body measurement sync.** **DoD:** source/state visible.
- [ ] **T17-012 [P1] Implement sync on/off and “Manage access”.** **DoD:** user control matches Android guidance.
- [ ] **T17-013 [P1] Implement background sync/checkpoints.** **DoD:** WorkManager/native approach documented, battery safe.
- [ ] **T17-014 [P1] Build connected-source status under `/you/integrations`.** **DoD:** last sync/error/permissions visible.
- [ ] **T17-015 [P1] Build connected trend cards.** **DoD:** deterministic calculations, missingness visible.
- [ ] **T17-016 [P1] Add AI trend explanation task behind flag.** **DoD:** device data != diagnosis; abstains on insufficiency.
- [ ] **T17-017 [P1] Add device/source-change detection.** **DoD:** trend explanation qualified.
- [ ] **T17-018 [P1] Keep Health Connect Medical Records separate experimental flag.** **DoD:** runtime feature availability and store-policy readiness check.
- [ ] **T17-019 [P2] Design HealthKit adapter interface.** **DoD:** same canonical envelope; no iOS-specific downstream semantics.

---

## EPIC 18 — Mobile consumer rebuild

- [ ] **T18-001 [P0] Replace feature-card mobile Home mental model.** **DoD:** daily priorities + Ask + recent changes/schedule.
- [ ] **T18-002 [P0] Implement bottom nav Home/Health/Ask/Care/You.** **DoD:** role-safe personal mode.
- [ ] **T18-003 [P0] Implement central Ask action.** **DoD:** text + native camera/file/voice affordances as supported.
- [ ] **T18-004 [P0] Implement mobile Health overview.** **DoD:** same state/provenance semantics as web.
- [ ] **T18-005 [P0] Implement mobile timeline.** **DoD:** pagination, filters, large text.
- [ ] **T18-006 [P0] Implement mobile medication hub.** **DoD:** no duplicate CareGuard/Self-Med launcher cards.
- [ ] **T18-007 [P0] Implement mobile results/measurements.** **DoD:** accessible charts/text.
- [ ] **T18-008 [P0] Implement mobile Care/visits.** **DoD:** visit prep parity.
- [ ] **T18-009 [P0] Implement mobile You/privacy/sharing.** **DoD:** permission/integration settings reachable.
- [ ] **T18-010 [P0] Implement professional-mode transition.** **DoD:** Council/Scribe not in personal Home buffet.
- [ ] **T18-011 [P0] Consolidate consumer terminology into localization layer.** **DoD:** no significant hard-coded VI strings in new core screens.
- [ ] **T18-012 [P0] Add Flutter accessibility semantics tests/manual checklist.** **DoD:** TalkBack/large text/touch targets.
- [ ] **T18-013 [P0] Add deep-link migration for legacy feature notifications.** **DoD:** routes land in canonical screens.
- [ ] **T18-014 [P1] Add secure offline emergency-card cache.** **DoD:** user-selected, encrypted, last-updated, no broad record cache.

---

## EPIC 19 — Notifications and proactive support

- [ ] **T19-001 [P1] Define server notification schema.** category/severity/key/params/action/dedupe/expiry. **DoD:** no raw arbitrary health prose requirement for new notifications.
- [ ] **T19-002 [P1] Define preference categories.** medication, visit, review, results, safety, sync. **DoD:** user can understand each.
- [ ] **T19-003 [P1] Implement quiet hours and category controls.** **DoD:** safety exception policy explicit.
- [ ] **T19-004 [P1] Implement dedupe/bundling for non-urgent notifications.** **DoD:** deterministic floor.
- [ ] **T19-005 [P1] Add notification deep-link target validation.** **DoD:** profile/authorization rechecked.
- [ ] **T19-006 [P1] Add notification analytics without health values.** **DoD:** payload audit.
- [ ] **T19-007 [P1] Add reminder snooze/pause flows.** **DoD:** no guilt copy.
- [ ] **T19-008 [P2] Pilot AI wording/bundling only for non-urgent categories.** **DoD:** deterministic timing/severity unaffected.

---

## EPIC 20 — Professional mode

- [ ] **T20-001 [P0] Create professional layout distinct from consumer shell.** **DoD:** explicit context banner and role checks.
- [ ] **T20-002 [P0] Preserve advanced Chat/Research controls in professional/research mode.** **DoD:** removed only from ordinary users, not destroyed.
- [ ] **T20-003 [P0] Rename Council presentation to user-friendly professional label.** **DoD:** internal APIs can retain current names.
- [ ] **T20-004 [P0] Integrate Council entry into case context.** **DoD:** fewer navigation hops.
- [ ] **T20-005 [P0] Preserve Scribe consent-before-mic.** **DoD:** regression E2E.
- [ ] **T20-006 [P0] Preserve draft vs attested/signed wording.** **DoD:** model output never implied final.
- [ ] **T20-007 [P0] Simplify Scribe workflow UI.** consent -> capture -> draft -> review -> attest/export. **DoD:** state machine explicit.
- [ ] **T20-008 [P0] Prevent patient/profile context confusion.** **DoD:** professional actions show active case/patient and server validates.
- [ ] **T20-009 [P1] Integrate evidence/Ask context into professional case view.** **DoD:** source provenance preserved.
- [ ] **T20-010 [P0] Add role/mode E2E.** **DoD:** normal cannot reach privileged actions; privileged personal mode stays personal.

---

## EPIC 21 — Landing, onboarding and activation

- [ ] **T21-001 [P0] Rewrite landing around consumer jobs.** Understand, remember, prepare, act safely. **DoD:** no module carousel as primary explanation.
- [ ] **T21-002 [P0] Replace technical hero preview.** **DoD:** shows realistic question/source/unknown/next-action pattern, no fake medical claims.
- [ ] **T21-003 [P0] Explain trust model simply.** source, limits, privacy, clinician role. **DoD:** no architecture jargon.
- [ ] **T21-004 [P0] Design goal-first onboarding.** **DoD:** user can pick what they need help with.
- [ ] **T21-005 [P0] Make nonessential medical profile steps skippable.** **DoD:** Ask/general/document explanation still accessible.
- [ ] **T21-006 [P0] Add contextual “why we ask” helper.** **DoD:** only when data is needed.
- [ ] **T21-007 [P0] Add first-document/medication capture option.** **DoD:** optional and review-first.
- [ ] **T21-008 [P1] Add connected-health setup option.** **DoD:** skip allowed; permissions not bulk-requested.
- [ ] **T21-009 [P0] Add notification preference explanation before OS prompt.** **DoD:** user action drives platform permission request.
- [ ] **T21-010 [P0] Instrument first-value funnel.** **DoD:** no PHI in events.
- [ ] **T21-011 [P0] Add onboarding E2E skip/complete/permission-decline.** **DoD:** no dead end.

---

## EPIC 22 — Security, privacy and abuse hardening

- [ ] **T22-001 [P0] Audit all new model secrets/endpoints.** **DoD:** server-only, secret scanner passes.
- [ ] **T22-002 [P0] Add provider base-URL allowlist validation.** **DoD:** SSRF/arbitrary endpoint tests.
- [ ] **T22-003 [P0] Validate TLS/secure transport configuration.** **DoD:** production deployment check.
- [ ] **T22-004 [P0] Add cross-profile cache poisoning tests.** **DoD:** profile switch/revoke cannot expose cached data.
- [ ] **T22-005 [P0] Add artifact ID authorization tests.** **DoD:** guessed ID cannot access another profile.
- [ ] **T22-006 [P0] Add upload bomb/oversize tests.** **DoD:** bounded resource consumption.
- [ ] **T22-007 [P0] Add malicious filename/content-type tests.** **DoD:** safe storage/display.
- [ ] **T22-008 [P0] Add prompt-injection tool-exfiltration tests.** **DoD:** model cannot invoke unauthorized tools/data.
- [ ] **T22-009 [P0] Add revoked-consent context reuse tests.** **DoD:** cached THSS/proposal cannot commit.
- [ ] **T22-010 [P0] Add public-share regression suite after route migration.** **DoD:** expiry/revoke/narrow scope preserved.
- [ ] **T22-011 [P0] Audit analytics fields.** **DoD:** automated test finds no raw prompt/document/value.
- [ ] **T22-012 [P0] Add gateway outage/circuit isolation test.** **DoD:** record browsing and deterministic safety remain available.
- [ ] **T22-013 [P0] Add CSRF/session regression to new writes.** **DoD:** existing protection retained.
- [ ] **T22-014 [P1] Add active-session revoke flow security tests.** **DoD:** session invalidates promptly.

---

## EPIC 23 — GLHS/read-write governance hardening for product AI

- [ ] **T23-001 [P0] Enumerate every AI task that can create a persistent proposal.** **DoD:** no unclassified writeback path.
- [ ] **T23-002 [P0] Require governed snapshot binding for those tasks.** **DoD:** proposal schema rejects missing binding.
- [ ] **T23-003 [P0] Include subject/profile/purpose in binding semantics.** **DoD:** tests wrong subject/purpose.
- [ ] **T23-004 [P0] Include consent/policy version/digest required by current GLHS contract.** **DoD:** revocation invalidates proposal.
- [ ] **T23-005 [P0] Preserve effective and recorded times in proposals.** **DoD:** temporal tests.
- [ ] **T23-006 [P0] Recheck authorization/consent at real DB commit transaction.** **DoD:** TOCTOU integration test.
- [ ] **T23-007 [P0] Test concurrent profile-state changes.** **DoD:** stale commit rejected or explicitly reconciled.
- [ ] **T23-008 [P0] Test revoked capture artifact/proposal reuse.** **DoD:** fail closed.
- [ ] **T23-009 [P0] Test digest/schema/canonicalization mismatch.** **DoD:** invalid proposal cannot commit.
- [ ] **T23-010 [P0] Add audit reconstruction for multimodal proposal.** **DoD:** source artifact -> model run -> review -> commit traceable.
- [ ] **T23-011 [P0] Ensure consumer UI explains rejection without protocol jargon.** **DoD:** preserves user edit and says information changed/permission changed.
- [ ] **T23-012 [P0] Keep product implementation aligned with research contract without exposing research nomenclature.** **DoD:** code comments/ADR map terms explicitly.

---

## EPIC 24 — Performance and resilience

- [ ] **T24-001 [P0] Set new route bundle budgets.** **DoD:** budgets based on measured baseline.
- [ ] **T24-002 [P0] Lazy-load multimodal preview/heavy chart code.** **DoD:** Home initial JS not inflated unnecessarily.
- [ ] **T24-003 [P0] Measure `/api/v2/home` p50/p95.** **DoD:** slow optional sources isolated.
- [ ] **T24-004 [P0] Add Ask perceived-progress states.** **DoD:** truthful, no fake “clinical analysis 67%”.
- [ ] **T24-005 [P0] Bound all model task timeouts.** **DoD:** timeout mapped to safe UX.
- [ ] **T24-006 [P0] Add upload cancellation and resumable/idempotent retry where practical.** **DoD:** no duplicate commits/artifacts.
- [ ] **T24-007 [P0] Optimize timeline pagination/virtualization if necessary.** **DoD:** large synthetic records remain responsive.
- [ ] **T24-008 [P0] Add image/PDF preprocessing resource limits.** **DoD:** memory/CPU stress tests.
- [ ] **T24-009 [P0] Measure Core Web Vitals on consumer routes.** **DoD:** p75 targets met or exception documented.
- [ ] **T24-010 [P0] Test provider outage.** **DoD:** Home/Health/medication deterministic core remains usable.
- [ ] **T24-011 [P1] Test offline mobile emergency-card behavior.** **DoD:** correct last-updated/stale signal.

---

## EPIC 25 — Analytics, quality and observability

- [ ] **T25-001 [P0] Define rebuild event taxonomy.** **DoD:** event names, fields, privacy classification.
- [ ] **T25-002 [P0] Instrument Home action funnel.** **DoD:** no health text.
- [ ] **T25-003 [P0] Instrument Ask modality/outcome.** **DoD:** no prompt contents.
- [ ] **T25-004 [P0] Instrument capture funnel.** upload -> extraction -> review -> accept/edit/reject -> commit. **DoD:** source type only, no document content.
- [ ] **T25-005 [P0] Instrument visit-prep completion.** **DoD:** no question text.
- [ ] **T25-006 [P0] Instrument sharing flow completion/error.** **DoD:** no recipient identity in product analytics.
- [ ] **T25-007 [P0] Create safety dashboard.** stale rejects, consent rejects, emergency floor, medication blocks, verifier failures. **DoD:** PII-safe.
- [ ] **T25-008 [P0] Create model route dashboard.** probe/latency/schema invalid/fallback/eval version. **DoD:** alias/version drift visible.
- [ ] **T25-009 [P0] Create sync dashboard.** Health Connect success/revoke/error/dedupe. **DoD:** no raw values.
- [ ] **T25-010 [P0] Add alerting for critical regressions.** cross-profile test failure, route probe failure, unsafe schema regression. **DoD:** actionable runbook links.
- [ ] **T25-011 [P1] Add user comprehension/usability research metrics repository.** **DoD:** findings can affect backlog without mixing with clinical claims.

---

## EPIC 26 — Testing and release gates

- [ ] **T26-001 [P0] Build new consumer route matrix checker.** **DoD:** canonical/redirect/professional/admin classification validated in CI.
- [ ] **T26-002 [P0] Add Home E2E.** active/empty/error/critical/profile. **DoD:** all supported viewports.
- [ ] **T26-003 [P0] Add Ask E2E.** general/personal/cancel/outage/source disclosure. **DoD:** no internal modes normal role.
- [ ] **T26-004 [P0] Add Health E2E.** current/history/conflict/source/timeline filters. **DoD:** stable fixtures.
- [ ] **T26-005 [P0] Add medication E2E.** active/stopped/scanned/unconfirmed/interaction. **DoD:** safety semantics exact.
- [ ] **T26-006 [P0] Add result E2E.** value/range/trend/no-range/explanation. **DoD:** numeric fidelity.
- [ ] **T26-007 [P0] Add capture E2E.** image/PDF/failure/edit/reject/commit. **DoD:** review-first.
- [ ] **T26-008 [P0] Add care/visit prep E2E.** **DoD:** stale source invalidation.
- [ ] **T26-009 [P0] Add sharing/revoke E2E.** **DoD:** post-revoke access denied.
- [ ] **T26-010 [P0] Add professional-mode E2E.** **DoD:** consumer/pro context separated.
- [ ] **T26-011 [P0] Expand axe smoke to every top-level rebuilt route.** **DoD:** no serious/critical violations or approved exception.
- [ ] **T26-012 [P0] Manual keyboard audit.** **DoD:** checklist evidence.
- [ ] **T26-013 [P0] Manual screen-reader audit on critical flows.** **DoD:** evidence and fixes.
- [ ] **T26-014 [P0] Mobile TalkBack/large-text audit.** **DoD:** critical flows usable.
- [ ] **T26-015 [P0] Visual regression baseline.** **DoD:** desktop/tablet/mobile no-PHI fixtures.
- [ ] **T26-016 [P0] Run all existing medication/consent/RBAC/GLHS suites.** **DoD:** no regression.
- [ ] **T26-017 [P0] Run real PostgreSQL concurrency gates.** **DoD:** bounded writes + AI commit TOCTOU pass.
- [ ] **T26-018 [P0] Run model locked evaluations.** **DoD:** each production route above threshold.
- [ ] **T26-019 [P0] Verify rollback drill.** **DoD:** UI/model/API can return to prior known-good state.
- [ ] **T26-020 [P0] Produce release evidence bundle.** **DoD:** checksums, versions, test results, route/model config, known limitations.

---

## EPIC 27 — Controlled rollout and legacy retirement

- [ ] **T27-001 [P0] Enable internal-only consumer shell V2.** **DoD:** no production consumer exposure.
- [ ] **T27-002 [P0] Dogfood Home/Health/Ask with synthetic/test accounts.** **DoD:** blocking issues triaged.
- [ ] **T27-003 [P0] Start 5% eligible UI canary.** **DoD:** stop conditions monitored.
- [ ] **T27-004 [P0] Review canary error/usability/safety metrics.** **DoD:** documented go/no-go.
- [ ] **T27-005 [P0] Expand UI to 25%.** **DoD:** no stop condition.
- [ ] **T27-006 [P0] Expand UI to 50%.** **DoD:** performance/support stable.
- [ ] **T27-007 [P0] Expand UI to 100%.** **DoD:** all P0 release gates satisfied.
- [ ] **T27-008 [P0] Promote Gemini route per task only after separate shadow/canary.** **DoD:** no blanket model switch.
- [ ] **T27-009 [P0] Monitor legacy route traffic.** **DoD:** source of remaining traffic understood.
- [ ] **T27-010 [P0] Verify supported old-client usage before API retirement.** **DoD:** minimum-client gate satisfied.
- [ ] **T27-011 [P0] Remove a legacy route only after retirement checklist passes.** **DoD:** import search/tests/build clean.
- [ ] **T27-012 [P0] Remove obsolete duplicated UI components only after replacement parity.** **DoD:** no dead import/flag.
- [ ] **T27-013 [P0] Consolidate feature flags after observation window.** **DoD:** rollback implications documented.
- [ ] **T27-014 [P0] Update production runbooks/support docs.** **DoD:** common user/model/sync failure procedures covered.

---

## EPIC 28 — Post-P0 product intelligence (P1/P2)

- [ ] **T28-001 [P1] Weekly/monthly grounded health digest.** **DoD:** source revision digest, stale invalidation, no diagnosis.
- [ ] **T28-002 [P1] “What changed?” natural-language comparison.** **DoD:** deterministic diff is authoritative.
- [ ] **T28-003 [P1] Contradiction/missing-information assistant.** **DoD:** surfaces review, never chooses truth automatically.
- [ ] **T28-004 [P1] Personalized evidence explanation.** **DoD:** applicability/missing facts explicit.
- [ ] **T28-005 [P1] Preventive-care reminders from approved deterministic rules.** **DoD:** rule source/version and locale applicability documented.
- [ ] **T28-006 [P1] Intelligent notification bundling.** **DoD:** no urgent timing/severity change.
- [ ] **T28-007 [P1] Natural-language record search.** **DoD:** temporal/profile-aware retrieval.
- [ ] **T28-008 [P1] Low-burden next-best-question ranker shadow test.** **DoD:** deterministic eligibility remains authority.
- [ ] **T28-009 [P2] Pattern relationship explorer.** **DoD:** descriptive/non-causal, minimum paired observations and uncertainty.
- [ ] **T28-010 [P2] Personal anomaly challenger.** **DoD:** shadow-only until calibration/false-alert evidence.
- [ ] **T28-011 [P2] Low-risk wellness forecast research.** **DoD:** no disease/treatment prediction; intervals/OOD/abstention.
- [ ] **T28-012 [P2] Trial/guideline matching pilot.** **DoD:** “possible match for review”, no inferred missing sensitive facts.
- [ ] **T28-013 [P2] Local/on-device privacy classifier/redaction preview.** **DoD:** benchmarked utility/privacy/device cost.
- [ ] **T28-014 [P2] HealthKit/iOS implementation.** **DoD:** connector contract parity with Health Connect.

---

## Global definition of done for every task that changes user behavior

Before checking any user-facing task complete, verify all applicable items:

- [ ] VI and EN copy exists and semantic parity is reviewed.
- [ ] Loading, empty, success, error and permission-denied states are implemented.
- [ ] Keyboard/touch/screen-reader behavior is considered and tested.
- [ ] Active profile/person is unambiguous.
- [ ] Server authorization remains authoritative.
- [ ] No PHI is added to URL or analytics.
- [ ] No fake health data is used as production fallback.
- [ ] Source/provenance/state is displayed where consequential.
- [ ] AI uncertainty is not presented as arbitrary medical confidence.
- [ ] AI writes are reviewable and GLHS-bound where applicable.
- [ ] New external/unofficial model behavior has a safe outage path.
- [ ] Unit/contract tests pass.
- [ ] Relevant E2E passes.
- [ ] Existing safety regression suites pass.
- [ ] Feature flag/rollback behavior is verified.
- [ ] Documentation/decision log is updated for material design deviations.

