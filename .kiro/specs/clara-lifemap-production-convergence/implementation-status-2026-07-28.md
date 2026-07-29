# CLARA LifeMap Production Convergence — Implementation Status

Date: 2026-07-28
Status: foundation milestone implemented and repository-tested; general
availability is not approved

This record separates implemented engineering from work that requires clinical,
privacy, security, operational, or prospective-study evidence. It must not be
used as a production-release approval.

## Implemented in this milestone

- Added the 16 server-authoritative LifeMap V2/AI capability flags. Every flag
  defaults off and is projected consistently through profile and mobile
  capability responses.
- Added opaque public identifiers, lifecycle/version fields, source references,
  append-only event revisions and task actions, command records, projection
  dependencies, and durable outbox state through additive migration
  `20260728_0030_lifemap_v2_foundation`.
- Added profile-scoped LifeMap resolution with non-enumerating denial behavior.
  LifeMap, evidence-question, and Family task/episode paths accept canonical
  opaque identifiers while retaining bounded legacy compatibility.
- Added deterministic truth/task state machines and typed confirm, correct,
  dispute, invalidate, resolve, accept, complete, episode, and task commands.
  Generic capture can no longer self-assert confirmed truth.
- Added request-digest idempotency, optimistic concurrency, stable error codes,
  command status lookup, atomic command/outbox persistence, and append-only
  history queries.
- Replaced the API-hosted LifeMap relay with a separately deployable worker,
  leased claims and owner-scoped heartbeats, retry/backoff, dead-letter state,
  HTTP liveness/readiness endpoints, and audited admin
  health/inspect/replay/resolve operations.
- Converged opaque LifeMap identifiers through evidence, insights,
  next-best-question, visit-plan confirmation, and Family delegation flows.
- Reclassified the Council “neural” shadow scorer truthfully as a fixed-weight,
  untrained heuristic while preserving its legacy alias and shadow containment.
- Updated browser E2E fixtures to use authenticated production-style API mocks
  and canonical Today, LifeMap, and Medicines routes.
- Fixed Flutter lifecycle, accessibility, reduced-motion, Material-version, and
  test-harness defects encountered by the unified mobile path.
- Corrected stale operational documentation links and the docs checker’s URL
  false positive.
- Made the ML production image consume the committed frozen dependency lock,
  preventing untested framework upgrades during deployment.

## Verification evidence

| Gate | Result |
| --- | --- |
| API full regression | 1,113 passed; 38 deprecation/OpenAPI warnings |
| API changed-path regression after final edits | 17 passed |
| API Ruff | Passed for `src` and `tests` |
| LifeMap/Family focused mypy | Passed for seven changed foundation modules |
| ML full regression | Passed |
| Council heuristic tests | Included in the passing ML regression suite |
| Web unit | 566 passed across 59 files |
| Web lint | Passed with five existing warnings |
| Web production build | Passed |
| Browser E2E | 6 passed; 2 expected device-specific skips |
| Flutter analyze | Passed |
| Flutter tests | 411 passed |
| Android release build | Passed against `https://theclaracare.com` |
| Migration rehearsal | SQLite upgrade, downgrade, and re-upgrade passed |
| Documentation links | Passed |
| Diff whitespace | Passed |
| Production PostgreSQL migration | Upgraded to `20260728_0030`; all public-ID reconciliation counts were zero |
| Production smoke | Web/API/ML/worker healthy; authenticated Today/capabilities/outbox passed |

Release APK:

- Path:
  `apps/mobile/build/app/outputs/flutter-apk/app-release.apk`
- SHA-256:
  `9ebef23c5f945ca9de87a93702d3ba9ce967b5dfd9dc7794d452cdb88647afa2`
- API base:
  `https://theclaracare.com`

## Known repository-wide quality debt

The service-scoped gates above are green. The root lint configuration currently
reports 602 historical findings across ML and utility scripts, and the full API
mypy run reports 188 historical errors across 24 files. The changed LifeMap
foundation modules are clean under their focused checks. These baselines were
not mass-rewritten because doing so would mix unrelated behavior changes into
this safety-sensitive milestone.

The API suite also reports existing FastAPI/Starlette deprecations and duplicate
OpenAPI operation-ID warnings. They are non-failing, but should be resolved in a
separate compatibility cleanup.

## Approval-gated and not complete

The unchecked tasks in `tasks.md` remain real work. In particular, the
following cannot be declared complete from repository implementation alone:

- intended-use, regulated-software, hazard, privacy, retention, and
  jurisdiction approvals;
- Universal Capture artifact security and field-level clinical evaluation;
- clinically selected baseline/question rules and Vietnamese/English usability
  pilots;
- grounded visit extraction evaluation;
- FHIR R4/IPS terminology licensing and conformance certification;
- penetration, load/soak, backup/restore, revocation-SLO, and production-like
  no-PII trace evidence;
- production shadow comparison, allowlisted rollout, kill-switch ownership, and
  rollback-window evidence;
- governed model/dataset/artifact registry, signed artifacts, prospective AI
  evaluation, and any predictive/adaptive research.

All new LifeMap V2 and AI flags therefore remain off. No unchecked task should
be converted to complete until its task-level definition of done and phase exit
gate are evidenced.

## Phase 11 interoperability engineering update — 2026-07-29

The implementable FHIR R4 boundary is complete without overstating IPS
conformance:

- a pure `clara-lifemap-fhir-r4-v1` mapper projects the canonical profile into
  Patient, Observation, AllergyIntolerance, Condition, MedicationStatement,
  CarePlan, Goal, Task, QuestionnaireResponse, DocumentReference, Provenance,
  Consent, and AuditEvent resources;
- every generated collection Bundle passes the in-process fail-closed
  structural/security validator before export;
- the committed golden fixture passed the official validator CLI `6.9.12`
  (SHA-256
  `0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6`)
  against FHIR R4 `4.0.1` with zero errors;
- imports are bounded to 1 MB, 500 entries, and 20 nesting levels and create
  only provenance-bearing, untrusted Capture drafts;
- security tests reject modifier/contained semantics, unknown elements,
  external/versioned/dangling references, duplicate full URLs, unsafe
  narrative, incomplete codes, non-UCUM quantities, excess size/depth, and
  ambiguous patient identity;
- export/import are independent, default-off capabilities and export is
  purpose-bound, consent-gated, profile-authorized, audited, and
  minimum-necessary; and
- the machine-readable conformance boundary, toolchain lock, mapping guide,
  upgrade procedure, validator script, and golden fixture are committed.

The IPS candidate is pinned to `hl7.fhir.uv.ips#2.0.1`, but task 11.1 remains
open for terminology/licensing approval and task 11.3 remains open because no
IPS claim may be made before the candidate document Bundle passes the IPS
package and named clinical/interoperability/privacy/legal sign-offs. The
`/export/ips` route therefore fails closed with
`ips_conformance_not_approved`. This is an intentional release gate, not an
implementation omission.

## Phase 12 client contract and offline boundary — 2026-07-29

The API, web, and Flutter clients now share
`lifemap-client-contract-v1`: `draft`, `awaiting_review`, `confirmed`,
`disputed`, `stale`, `unavailable`, and `offline`. Only `confirmed` has truth
authority; Flutter maps an unknown future value to `unavailable`. The same
content-free endpoint publishes server-authoritative feature availability and
the online-only mutation policy.

Flutter now has a default-off, platform-secure-storage LifeMap Today read
cache. It projects only task/episode display fields and counts, has `cached_at`
and a 15-minute `valid_until`, is always visibly offline, becomes visibly stale
after expiry, disables completion, and is erased on logout/account switch.
Tests prove excluded provenance, medication, safety, and arbitrary payload
fields are not stored. Web deliberately has no persisted LifeMap health cache
until an approved encrypted browser store exists; it therefore cannot leak a
health projection into local/session storage. Queued health mutations remain
unsupported on both clients.

Tasks 12.2 and 12.3 remain open pending the final all-module accessibility and
responsive evidence sweep. Task 12.6 remains a real bilingual usability study,
not a repository test.

## Production deployment evidence

The foundation was deployed to `https://theclaracare.com` on 2026-07-28.

- Public `/` and `/login` returned 200; authenticated destinations returned the
  expected 307 login redirect; a versioned Next.js asset returned 200.
- Authenticated profile capabilities and Today returned 200.
- All 16 new LifeMap V2/AI flags were present and false.
- Outbox operational health returned `ok`, with zero pending and zero
  dead-letter rows.
- API, ML, web, and the standalone LifeMap worker were healthy, with no
  traceback/fatal/panic log matches in the post-deployment window.
- The worker health timeout was raised from 5 to 15 seconds after production
  showed that cold Python imports could narrowly exceed five seconds on the
  one-core host. The database probe itself remained successful.
- Rollback artifacts are stored on the VPS under
  `/opt/clara-care/backups/pre-lifemap-v2-20260728-180210-*`: a validated
  PostgreSQL custom-format dump, source snapshot, and SHA-256 manifest.

A follow-up API/worker rollout on the same date added the owner-scoped lease
heartbeat, real `/health/live` and `/health/ready` worker probes, retry-budget
reset on audited replay, and audited terminal dead-letter resolution.
Post-deployment evidence showed:

- worker liveness and readiness both returned 200;
- authenticated outbox health returned `ok`, with zero pending and zero
  dead-letter rows and the new resolved counter present;
- PostgreSQL remained at migration head `20260728_0030`;
- public `/` and `/login` returned 200; and
- API and worker logs contained no traceback, unhandled, fatal, or panic
  matches.

Task 3.2 was subsequently completed with a real concurrent PostgreSQL
`SKIP LOCKED` contract. Four simultaneous workers claimed 64 isolated test rows
without overlap or loss, then a recovery worker reclaimed exactly one expired
lease. The test created and dropped a randomly named schema and did not read or
mutate production application tables.

The next worker tranche completed the versioned `lifemap.outbox.v1`
minimum-data envelope and typed event-kind classification for fact, episode,
task, consent, correction, and invalidation changes. Extra fields are forbidden,
which regression-locks that clinical payloads cannot be added to delivery
envelopes accidentally. Worker-local health now exposes bounded no-PII outcome
and cycle-duration metrics, while the admin database health projection exposes
pending/retry/processing/published/dead-letter/resolved counts, expired leases,
aggregate retry attempts, oldest unpublished age, and stale projection
dependencies. Alert thresholds, scaling, incident response, and rollback are
documented in `docs/runbooks/lifemap-outbox-worker.md`.

Phase 3 failure and recovery coverage was then completed. The only deployed
consumer is the stateless no-PII structured-log publisher; completed rows are
never selected again. Tests cover FIFO ordering, duplicate drains, isolated
dependency failure without head-of-line blocking, immediate recovery, expired
lease reclaim, retry exhaustion, terminal dead-letter state, audited replay,
and bounded aggregate metrics. An isolated PostgreSQL soak ran 20 complete
four-worker claim/recovery cycles (1,280 rows) in 5.595 seconds with disjoint
claims, complete reconciliation, exactly-once expired-lease recovery, and
random schemas dropped after every cycle. This is worker engineering evidence,
not a substitute for the later GA load/SLO certification gate.

Phase 1 scope hardening now includes an explicit `ProfileAccessPolicy`.
Ownership, caregiver grants, and clinician grants are distinct server-derived
actor classes. Doctor role alone grants nothing; a doctor needs a live,
purpose-bound, action-scoped LifeMap grant. Administrative role is explicitly
denied for non-owned health profiles even if a Family grant exists, preserving
the separate audited break-glass boundary. V2 serializers and resolvers return
opaque public identifiers, with numeric resolution retained only inside bounded
legacy compatibility adapters.

Phase 1 is now closed at the repository gate. Public-ID reconciliation has a
bounded, resumable operator command; all LifeMap object routes resolve
server-authorized profile scope; Family grants persist explicit data classes,
actions, purpose, expiry, and grant version; revocation takes effect on the
next request; and object reads/changes plus denied support access append
minimum-data audit records. The IDOR, enumeration, confused-deputy, invitation
replay, expiry, revocation, and cross-profile worker boundaries are documented
in `docs/security/lifemap-v2-threat-model.md` and regression-tested.

Phase 2 is also closed at the repository gate. Exact decision-to-revision links
complete the additive provenance schema. Legacy facts receive explicit
unverified certainty rather than fabricated confirmation and have a no-PHI
aggregate reconciliation report. Generic capture cannot assert confirmation;
confirm, correct, dispute, invalidate, and resolve are typed commands with
stable failure codes. The command transaction binds scope, actor, digest,
idempotency, optimistic version, audit, canonical write, and outbox. Tests lock
append-only revisions, immutable source checksums, one canonical revision
pointer, idempotency conflicts, and rollback of canonical data when outbox
creation fails.

Universal Capture now has its first complete backend tranche behind
`LIFEMAP_CAPTURE_ENABLED` (still default OFF). Migration `20260728_0033` adds
resumable sessions, encrypted artifact metadata, durable extraction jobs,
review-only candidates, and append-only review actions. Artifact bytes require
AES-GCM object storage, exact media sniffing, bounded size, a clean fail-closed
ClamAV verdict, checksum, authenticated short-lived access, and expiry/abandon
deletion. Text capture runs a deterministic Vietnamese/English emergency
fast-path before profile, consent, or persistence. Typed extraction schemas
cover text, medication labels, visit documents, guided answers, and imported
observations; job output remains draft with confidence, exact source span,
missing-critical-field, extractor-version, and prompt-injection findings.
Exact-checksum duplicates are suggestions only and never auto-merge.

The initial web and Flutter review surfaces are server-capability-gated and
preserve the explicit-confirmation boundary. Their focused lint/analyze and
client tests pass. Phase 4.5 and the complete 4.7–4.9 gates remain open because
production OCR/ML worker wiring, full artifact review UX, and field-level
clinical evaluation evidence are not yet complete.

The Phase 5 canonical Replay foundation is implemented behind the existing
dark rollout controls. Migration `20260728_0034` adds append-only episode goal
revisions, exact episode-to-event-revision membership, and opaque public IDs for
decision-ledger reads. Episode creation and goal changes are idempotent,
optimistically concurrent commands; event creation can attach to an authorized
open episode; and every truth transition or correction atomically supersedes
the old replay link and points to the replacement revision. The Replay query
uses those exact revisions and returns consumer-safe why text, provenance,
policy version, and derived-decision stale state without exposing model
chain-of-thought.

Web and Flutter now provide a revision-aware Health Replay reader and explicit
correction flow. Both explain that correction creates a new version; Flutter
also labels the mutation online-only and never queues a health write offline.
Focused API migration/behavior, web client/lint, and Flutter analyze/client
tests pass. Phase 5 is not yet closed: consent/source-revocation and late-data
invalidation traversal, the authorized dispute-resolution queue, complete
cross-client dispute handling, and the property-test gate remain open.

Phase 6 now has an approval-aware dark implementation. Migration
`20260728_0035` adds versioned baseline definitions, immutable snapshots, exact
aggregate inputs, explainable changes, typed question definitions, and
append-only interaction history. No production definition or question is
silently approved: V2 endpoints return no governed result unless a registry row
has explicit approval metadata, the server flag is on, and current medical
consent exists.

The baseline engine normalizes canonical units, rejects configured invalid
ranges, requires both sample count and calendar span, computes median and median
absolute deviation, hashes the exact input watermark, reuses identical
snapshots, and marks the predecessor stale after late/corrected data. It
describes only change against the same person's history, never clinical
normality. Property tests cover order independence and robust statistics.

The governed question engine selects at most one deterministic approved
question, preserves emergency short-circuiting, applies answered/dismissed/
do-not-ask filters, a 24-hour burden ceiling, and consent. A response creates a
`guided_answer` Capture candidate and cannot become truth until explicit review.
Web and Flutter surfaces are server-capability gated and explain both the
question rationale and the draft-review boundary. Focused API lint/type/tests,
web lint/client tests, and Flutter analyze/client tests pass. Clinical signal
and catalogue approval, historical shadow evaluation, and comprehension pilots
remain open, so both V2 flags stay default OFF.

The Phase 7 Medication Guardian convergence foundation is implemented through
migration `20260728_0036`. Medication courses now retain original product text,
normalization system/code, reconciliation status, route/form, source reference,
opaque public ID, and optimistic version. Create, correction, and end commands
are profile-scoped and idempotent; corrections and lifecycle changes append
immutable snapshots, and an owner-scoped history query exposes those versions
without database identifiers. Legacy rows are preserved, while unresolved
normalization is marked `unknown` rather than fabricated.

Medication DDI checks select current, confirmed, active courses by default.
Hypothetical names use an explicitly separate request and response mode, and
mixed real/hypothetical inputs are rejected. DrugBank readiness and exclusive
DrugBank provenance remain fail-closed. Web and Flutter now support route/form,
new-version correction, record-only course ending, and coherent
list/cabinet/safety tabs. The web cabinet's prior locally inferred risk score
and name-matched drug warnings were removed; it now reports only factual data
completeness/expiry and directs clinical checks through DrugBank/FIDES.

Focused evidence includes 10 API medication/migration/scope tests, 33 ML
CareGuard/FIDES/medical-answer safety tests, five web medication client/copy
tests, and sixteen Flutter wrapper/copy tests, plus clean focused lint, mypy,
and Flutter analysis. Phase 7.3 remains open until all OCR/import writers create
Universal Capture drafts with critical-field review. Phase 7.7 also remains open
until legacy-route traffic and the approved redirect/rollback window permit
retirement.

The Phase 8 Grounded Visit engineering path is now implemented behind
`LIFEMAP_VISIT_EXTRACTION_ENABLED`, which remains default OFF. Migration
`20260729_0037` gives visits, documents, concerns, links, intake answers,
drafts, packs, consents, and shares opaque identifiers; documents are
revisioned; and typed instruction candidates retain classification, confidence,
extractor/schema versions, review state, source digest, and exact
page/region/text spans.

The ML extractor is DeepSeek-backed and fail-closed. It rejects prompt-injection
content before model use, validates a bounded candidate-kind schema, and
returns no candidates if any output is malformed, ungrounded, or unavailable.
The API independently revalidates every exact source substring and digest.
Only a user-selected `clinician_instruction` may propose a task;
`model_interpretation` is visibly non-actionable. No source span means no
confirmation and no task.

Visit Packs now require explicit opaque selections and preserve an immutable,
purpose-bound V2 snapshot with visit, episode, event, medication, document,
and confirmed-instruction source versions. A source correction, medication
version change, or selected document withdrawal/deletion marks dependent packs
stale; stale packs cannot be approved, shared, or resolved through an existing
capability. Web and Flutter both implement document control, candidate review,
pack selection/approval, seven-day sharing, immediate revocation, and
visit-specific Scribe consent.

Focused Phase 8 evidence includes 14 API domain/migration/opaque-ID/grounding/
staleness tests, four ML extractor security/grounding tests, seven web client
contract tests, and four Flutter wire-contract tests, with clean focused Ruff,
mypy, web lint, and Flutter analysis. Tasks 8.3 and 8.7 remain open: the flag
must not be enabled until the governed source-span/safety evaluation establishes
instruction accuracy, unsupported-instruction rate, span validity, task
leakage, and user comprehension thresholds.

Phase 9 Family Circle engineering hardening is implemented through migration
`20260729_0038`. Invitations, grants, and access-log records now expose opaque
identifiers; internal user/profile/grant identifiers are removed from consumer
responses and provenance. Existing grants already enforce explicit data
classes, actions, purpose, start, expiry, version, and revocation. Authorization
is re-evaluated from canonical state on every request, so revoke/expiry removes
derived notification cards and denies the next API action without a cache,
session, or background-job delay.

Invitation and share capabilities remain hash-only at rest. Invitation
acceptance is recipient-bound and transactionally one-time: an idempotent replay
can return the same grant but cannot mint another; URL-carried capabilities are
never processed or echoed. Grant renewal never silently extends authorization:
it creates a fresh one-time invitation for the same minimum scope and requires
recipient acceptance again.

Owner-scoped share options prevent clients from inventing object identifiers.
Web and Flutter now create the same episode/visit scopes, display minimum-data
access activity, review active grants, revoke immediately, and create explicit
renewal capabilities. Focused evidence includes the existing data-class/action/
purpose authorization matrix plus ten Family API/migration/live-revocation
tests, three Flutter wire-contract tests, and nine web client-contract tests;
focused Ruff, mypy, web lint, and Flutter analysis pass.

Task 9.5 remains approval-gated. CLARA does not infer or implement a minor or
legal-representative relationship from ordinary Family Circle data; that use
case remains unsupported until privacy/legal policy approval and a separate
identity/authority proofing design exist.

Phase 10 Living Evidence engineering completion is implemented through
migration `20260729_0039`. Evidence questions, runs, records, subscriptions,
and guideline artifacts now expose opaque identifiers. Source identity is
stable across retrievals through normalized source class, provider, source ID,
and identifier digests; per-subscription checkpoints retain only bounded
cursors and watermarks.

Applicability is governed by versioned draft/approved/retired rules. Doctor or
admin approval is explicit, only one approved version remains active per
question class, and evaluation reads only confirmed LifeMap facts. A missing
approved rule, missing required fact, or invalid typed value returns
`not_assessed` or mismatch; CLARA does not infer a private fact to manufacture
eligibility.

The standalone `evidence-monitor` uses hour-bucket dedupe, leased
`SKIP LOCKED` claims, consent checks at schedule/claim/notification time,
bounded exponential retry, dead-letter, cancellation, and durable source
checkpoints. New or removed search results alone are not a material-change
notification. A versioned contradiction/material-change assessment remains
pending until a doctor or admin accepts it, at which point a minimum-data
in-app notification may be created if the subscription and consent remain
active.

Web and Flutter now support question confirmation and retrieval, durable
subscriptions, daily/weekly/monthly preferences, revocation, honest
applicability, contradiction visibility, and reviewed-change notifications.
Focused evidence includes nine API behavior/migration tests, eight web client
tests, and three Flutter wire-contract tests, plus clean focused Ruff, mypy,
web lint, and Flutter analysis. The worker and API flag remain default OFF and
the dark rollout/recovery procedure is documented in
`docs/runbooks/lifemap-evidence-monitor.md`.

Task 10.8 remains open. Citation validity, contradiction sensitivity,
applicability precision, notification usefulness, and stale-evidence failure
evaluation require a governed frozen dataset and Clinical Safety approval;
until those external gates pass, periodic execution must stay disabled.

This deployment does not enable approval-gated V2/AI capabilities and is not a
general-availability approval.
