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

This deployment does not enable approval-gated V2/AI capabilities and is not a
general-availability approval.
