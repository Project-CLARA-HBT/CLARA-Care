# Tasks — CLARA Product Experience Convergence

Unchecked tasks are incomplete. Human studies, production drills, and approvals
must not be checked from repository tests.
See [`traceability.md`](traceability.md) for requirement-to-phase and required
evidence mappings.

## Phase 0 — Baseline and governance

- [x] 0.1 Inventory active web routes, mobile surfaces, form-bearing pages, and
  existing wizard patterns.
- [x] 0.2 Research primary accessibility and current health AI/RAG evidence.
- [x] 0.3 Complete route-by-route task/reader/workspace/admin classification.
- [ ] 0.4 Capture approved desktop/mobile light/dark baseline screenshots.
- [ ] 0.5 Approve usability success measures: completion, time, abandonment,
  error recovery, comprehension, and safety—not clicks alone.
- [ ] 0.6 Approve the canonical role-aware navigation and legacy
  redirect/adapter/retirement map without duplicate primary entries.

## Phase 1 — Shared system

- [x] 1.1 Implement web `GuidedFlowShell`, accessible progress, actions, review,
  error summary, save state, and readiness primitives.
- [x] 1.2 Implement Flutter equivalents with phone/tablet/text-scale semantics.
- [x] 1.3 Add typed flow registries, step-order guards, stable analytics schema,
  and localized labels.
- [ ] 1.4 Add/reuse server draft envelopes, opaque IDs, revisions,
  idempotency, expiry, resume, and abandon.
- [x] 1.5 Add component/property/accessibility tests.

## Phase 2 — Modern light-mode foundation

- [x] 2.1 Freeze semantic light/dark canvas, surface, text, border, action,
  status, focus, elevation, radius, spacing, and typography tokens.
- [ ] 2.2 Replace hard-coded feature light colors and conflicting glass/glow
  compatibility styles on active surfaces.
- [ ] 2.3 Modernize shell, empty/loading/error states, cards, tables, forms,
  dialogs, drawers, and sticky mobile actions.
- [ ] 2.4 Pass automated contrast, 200% zoom/reflow, reduced-motion, forced-
  colors, and visual-regression matrices.
- [ ] 2.5 Run user/design review of light mode on real desktop and mobile.

## Phase 3 — Entry, account, and setup

- [ ] 3.1 Convert registration, verification, role, onboarding/profile basics,
  measurements, context, consent, and review into focused routes.
- [ ] 3.2 Split account consent and data rights into request/review/confirm/status
  routes with destructive-action safeguards.
- [ ] 3.3 Build consumer Setup/Feature Readiness guidance linking profile,
  consent, data import, optional wearable, medicines, and family steps without
  duplicating their domain flows.
- [ ] 3.4 Build Admin Setup Center with API/ML/RAG/provider/corpus/OCR/ASR/
  workers/email/storage/migration/flag checks.
- [ ] 3.5 Rehearse clean setup from documented environment to production smoke.

## Phase 4 — LifeMap and Today

- [ ] 4.1 Keep Today concise; add focused task/source detail routes.
- [ ] 4.2 Split LifeMap episode/event/task creation into short draft steps and
  review.
- [ ] 4.3 Split Universal Capture source/upload/process/field review/
  normalization/conflict/final confirmation.
- [ ] 4.4 Move Ask, summaries, Replay, baselines, and findings to focused routes
  or clearly progressive readers.
- [ ] 4.5 Remove duplicate in-page creation panels after web/mobile parity.

## Phase 5 — Medicines

- [ ] 5.1 Convert add medicine to method/identity/details/schedule/source/review.
- [ ] 5.2 Convert interaction checking to mode/select/context/review/result.
- [ ] 5.3 Add focused correct/end/import review flows.
- [ ] 5.4 Verify OCR drafts, normalization, unknowns, DDI/FIDES, and hypothetical
  separation across Back/resume/error paths.

## Phase 6 — Visits, Scribe, and Council

- [ ] 6.1 Convert visit creation/intake/documents/review/pack/share.
- [ ] 6.2 Convert Scribe purpose/consent/input/process/transcript/SOAP sections/
  review/export.
- [ ] 6.3 Standardize Council's existing wizard on shared primitives and split
  dense result sections.
- [ ] 6.4 Test consent-before-recording, source spans, correction, stale packs,
  and human review.

## Phase 7 — Family, PHR, Evidence, Community

- [ ] 7.1 Convert Family invite/authority/purpose/expiry/review and focused
  renew/revoke/access-log flows.
- [ ] 7.2 Convert PHR category/item/provenance/verification/review flows.
- [ ] 7.3 Convert Living Evidence topic/PICO/episode/review/run/subscription.
- [ ] 7.4 Convert Community create/report/moderation to safety-reviewed flows.
- [ ] 7.5 Prove revocation, unknown eligibility, moderation fail-closed, and
  truth-authority invariants.

## Phase 8 — Chat/RAG scientific convergence

- [ ] 8.1 Publish dated evidence notes and immutable manifests for Chat, RAG,
  embeddings, reranking, NLI, FIDES, Council, Scribe, Capture, and evidence
  matching.
- [ ] 8.2 Implement/finalize stage-level retrieval evaluation with non-RAG and
  deterministic baselines; report retrieval, selected-context,
  claim/citation, generation, safety, subgroup, latency, and cost stages with
  denominators and confidence intervals where applicable.
- [ ] 8.3 Select top-k/context policy from frozen precision/recall/faithfulness
  evidence; abstain/source-only below the context gate.
- [ ] 8.4 Add claim citation, entailment, temporal, contradiction, profile,
  legal, and FIDES release evidence for exact pipeline versions.
- [ ] 8.5 Add blinded native-Vietnamese clinician review, a private
  CLARA-grounded safety/citation set, and approved VM14K, ViMedAQA, and VIMQA
  slices without treating benchmark scores as clinical validation.
- [ ] 8.6 Run red-team, shadow, human-AI workflow, prospective evaluation where
  applicable, rollback, and post-release monitoring before promotion.
- [ ] 8.7 Schedule quarterly evidence review and change-triggered reevaluation.

## Phase 9 — Administration

- [ ] 9.1 Split RAG source registration, ingestion, evaluation, release review,
  and monitoring into focused routes.
- [ ] 9.2 Split DSAR, moderation, feature configuration, and destructive admin
  actions into reviewable tasks.
- [ ] 9.3 Keep analytics/observability as readers with progressive drill-down,
  not wizardized dashboards.
- [ ] 9.4 Test role scope, secret handling, immutable provider identity, audit,
  and rollback.

## Phase 10 — Validation, migration, and release

- [ ] 10.1 Complete web/mobile unit, integration, property, accessibility, and
  route E2E suites.
- [ ] 10.2 Complete light/dark screenshot review across desktop/phone/tablet,
  zoom/text scale, screen reader, keyboard, and reduced motion.
- [ ] 10.3 Run API/ML full tests and reconcile or explicitly baseline every
  repository-wide static failure.
- [ ] 10.4 Run clean database migration, worker, backup/restore, projection
  rebuild, load/soak, penetration, privacy, and no-PII telemetry drills.
- [ ] 10.5 Migrate users with redirects and resumable drafts; remove obsolete
  canvases only after telemetry and rollback window.
- [ ] 10.6 Update help/setup docs and complete bilingual usability testing.
- [ ] 10.7 Commit, push, deploy default-safe flags, run production smoke, and
  verify rollback.

## Exit gate

All active features have an appropriate focused flow or progressive reader,
light mode is approved and accessibility-clean, clean setup is rehearsed,
scientific AI evidence is current for exact versions, safety invariants pass,
legacy duplicates are retired, and production deployment/rollback evidence
exists.
