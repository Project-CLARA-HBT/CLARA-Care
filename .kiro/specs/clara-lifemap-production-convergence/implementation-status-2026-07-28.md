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

## Phase 15 ML-governance foundation — 2026-07-29

Migration `20260729_0040` adds versioned, append-only AI use-case definitions,
generic registry objects for datasets/features/training/artifacts/evaluations/
deployments/drift/feedback, private context-lineage manifests, and no-content
inference manifests. ORM update/delete hooks reject mutation; a changed record
must append a new version. SQLite full upgrade, downgrade to `0039`, and
re-upgrade to `0040` passed.

The committed `clara-ml-inventory-v1` catalog truthfully identifies 18 deployed
or staged capabilities: DeepSeek chat/research/Council, the Council fixed-weight
shadow heuristic, embeddings, reranking, NLI, FIDES, CareGuard DDI, three OCR
paths, three ASR paths, deterministic baselines/questions, and evidence-change
rules. Every entry includes provider/implementation, intended and forbidden
use, owner, risk, release state, flag, fallback, and data origin.

The governance library now provides:

- a forward-only promotion state machine with recall/retirement;
- purpose/consent/data-class/revision filtering before an ML context manifest
  can be compiled;
- a strict no-content operational-manifest allowlist;
- Ed25519 canonical-manifest verification, SHA-256 byte verification, artifact
  root containment, and approved-state enforcement;
- immutable provider-alias resolution and silent-provider-change detection;
- deterministic pseudonymized snapshot construction with consent/purpose
  rejection and person/household/site/source/device/window leakage audits; and
- mandatory use-case, datasheet, model-card, evaluation, and change-control
  templates plus incident/recall/fallback runbook.

The separate digest-pinned Python 3.11 offline-training image contains only
exact-pinned classical ML dependencies. PyTorch, notebooks, credentials, and
production OLTP access are intentionally absent pending an approved neural use
case.

Tasks 15.4 and 15.6 remain open: the verifier and snapshot builder are complete
foundations, but no existing live model may be relabeled “signed/governed”
until its real artifact is signed in an approved offline pipeline, wired to the
online loader/fallback, and a production-authorized audited snapshot job is
approved. No learned LifeMap feature is promoted by this work.

The implementation foundation now also includes an immutable signed bundle
store, atomic staging install, per-load signature/checksum re-verification,
server-owned champion/challenger/fallback resolution, deterministic safe
fallback, runtime provider allowlist parsing, and silent provider-identity
rejection. Dataset export can now write an immutable audited bundle outside
OLTP with recursive content rejection, separately keyed pseudonymization,
identity-connected split assignment, leakage audit, and tamper detection.
These close the code-path gaps but intentionally do not close Tasks 15.4 or
15.6: no real learned artifact, immutable DeepSeek provider revision, target
approval, or production-authorized export evidence has been supplied.

## Phase 12 accessibility convergence increment — 2026-07-29

The optimized web build now has a real LifeMap browser matrix on desktop and
Pixel 7 viewports. It verifies keyboard-first skip navigation, semantic
landmarks and labels, reduced-motion collapse, 200% text scaling without
horizontal overflow, and computed text contrast. The matrix exposed two real
intrinsic-sizing defects: the LifeMap one-column grid expanded to its content
minimum on mobile, and rem-scaled topbar controls overflowed desktop at 200%.
The grid now uses a zero-minimum track/children, command controls retain bounded
physical targets under zoom, and the focused skip link wraps within the
viewport. The complete optimized Playwright suite passes with 8 tests and 2
project-appropriate skips; the focused style suite passes 9 tests.

Flutter now mounts the real unified LifeMap surface with Ask, Capture, review,
baseline, episode, and task capabilities under phone, tablet, 1.6x text, screen
reader semantics, and reduced-motion configurations. All 10 focused widget
tests pass and `flutter analyze` is clean. Tasks 12.2 and 12.3 remain open
because every other V2 module and real-device screen-reader workflow has not
yet completed the same matrix.

## Universal Capture evaluation foundation — 2026-07-29

A versioned evaluator and frozen bilingual suite now exercise the actual
`grounded-ocr-baseline-v1` extractor and API emergency detector. The runner
reports field precision/recall, critical misses, wrong-medication rate, exact
span validity, emergency sensitivity/specificity and p95 latency, extraction
p95 latency, confirmation actions per case, and per-locale slices. Threshold
schema drift and malformed/draft-unsafe output fail closed; passing can never
grant promotion.

The 12-case synthetic contract suite currently passes every declared gate and
has a cross-service CI test. Task 4.9 remains open because this small synthetic
suite is not evidence for real OCR degradation, end-to-end network/worker
latency, observed confirmation burden, user comprehension, or clinical review.

## Phase 16 grounded Ask vertical slice — 2026-07-29

`POST /api/v1/lifemap/v2/ask` now resolves a server-owned use-case definition,
runs emergency and legal intent gates before health retrieval, resolves the
authorized `ProfileScope`, requires current medical consent, then applies
episode/time/profile filters before materializing current exact revisions.
Empty retrieval abstains. Emergency wording bypasses retrieval and returns the
existing escalation class. Diagnosis, prescribing, and personal-dose requests
are rejected.

The typed response separates claims from an evidence table and exposes unknown,
conflicting, stale, and disputed states, source attribution, disclosure,
abstention, verifier status, model/template/retrieval/policy identity, and exact
revision citations. Released claim text in this first slice is a deterministic
copy of its cited revision summary; no generative medication claim is created,
so FIDES is explicitly not applicable rather than falsely marked passed.
Citation existence and profile containment fail closed. A private
`AIContextManifest` and no-content `MLInferenceManifest` are appended for each
non-empty inference.

The default-off web experience reads the server capability and offers Ask only
when enabled, displaying per-claim source, time, revision, ambiguity warning,
and the non-medical/read-only disclosure. Five API contracts and seven focused
web client contracts pass; web lint passes with the five pre-existing warnings.

Tasks 16.2, 16.4, and 16.11 remain open: the current retrieval champion is
profile-partitioned lexical/temporal SQL, not yet the governed dense/graph
index; verifier integration for future generated claims still needs bounded
NLI/FIDES evaluation; and mobile Ask/review surfaces are not yet implemented.

The Flutter unified LifeMap surface now also reads `lifemap_ask_ai` from the
server summary, calls only the governed `/lifemap/v2/ask` contract, and renders
the read-only disclosure plus exact citation attribution/revision. It remains
hidden when the server flag is off. Focused Flutter analysis is clean and 22
API-client/accessibility-responsive tests pass. Task 16.11 stays open because
the broader summary, multimodal, normalization, and conflict-review experiences
are not yet complete.

The ML service now has a model-neutral `LifeMapExtractor` protocol and one
validated draft-only result contract shared by adapters for the current OCR,
ASR, document-layout, DeepSeek structured-extraction, and optional VLM
candidate paths. The boundary verifies the authorized artifact checksum,
modality/schema/field allowlists, confidence, units, text offsets, audio
timestamps, page regions, required-field missingness, and prompt-injection
candidates. Diagnostic-image interpretation is rejected at schema validation.
Four focused ML tests pass. Tasks 16.7 and 16.8 remain open until each production
backend is wired through this boundary and field-level evaluation proves the
degraded fallbacks.

The governed entity-resolution ensemble now performs Vietnamese diacritic and
whitespace normalization, exact/alias lookup, calibrated dense-candidate
merging, terminology-graph filtering, and bounded optional reranking. Dense
search or reranking cannot introduce an inactive/unknown/out-of-graph code;
reranking cannot raise calibrated confidence. Every candidate carries its
terminology system and mapping revision, close/low-confidence candidates remain
ambiguous, and no candidate is auto-confirmable. Four focused tests cover alias
resolution, graph containment, ambiguity, and unknown-code rejection.

The rule-first review engine now detects bounded-window duplicates and
contradictions from exact active revisions and reports required-field
missingness. Invalidated/superseded/error facts are excluded. Bounded NLI/LLM
proposals are accepted only when every referenced revision is already in the
authorized candidate set; they remain explicitly `model_proposal` findings
requiring human resolution and cannot change truth. Four focused unit tests
pass.

Migration `20260729_0041` now persists immutable, deduplicated findings and
append-only human actions. Profile-scoped, consent- and flag-gated API routes
scan current exact revisions, list effective status, and accept only explicit
`resolved`/`dismissed` actions with idempotency-conflict detection and PHR
audit. A repeated scan cannot duplicate a finding; a repeated action returns
the original result. Full SQLite upgrade, downgrade to `0040`, and re-upgrade
to `0041` passed. Five focused API tests pass. The web/mobile conflict-review
experience remains tracked under task 16.11.

The capability-gated web LifeMap surface now makes scanning an explicit user
action, labels duplicate/contradiction/missingness as possibilities rather than
truth, and exposes explicit reviewed/dismissed actions. It never edits source
facts. Eight focused web client contracts pass and web lint remains clean apart
from the five documented pre-existing warnings. Flutter conflict review and
the other Phase 16.11 experiences remain open.

Flutter now mirrors the explicit scan and online-only reviewed/dismissed
actions, with possible-not-certain wording and no source-fact mutation. Focused
analysis is clean and 23 API-client/accessibility-responsive tests pass.

The default-off summary API now builds event/day/episode/week/visit projections
from temporally ordered structured child claims. Every child retains exact
revision citation, attribution, and truth state; disputed/conflicting inputs
remain explicit. The deterministic fallback never converts absence into a fact.
Each summary has a content-derived opaque ID and deduplicated
`LifeMapProjectionDependency` rows, so the existing correction/invalidation
traversal marks every affected ancestor stale. Six focused Ask/summary API tests
pass with clean Ruff and mypy.

Web and Flutter now expose the default-off hierarchical summary contract with
day/week/selected-episode scopes, source identifiers, attribution, timestamps,
and non-confirmed truth states visible in the primary experience. Medication
capture also exposes a server-owned RxNorm proposal in both clients. A user may
accept or decline it, but cannot submit a code; confirmation recomputes the
mapping from the final edited medicine name, rejects unmapped acceptance, and
records the decision, policy, source, confidence, and structured course fields
in append-only provenance. Focused API, TypeScript, and Dart client tests pass.
Task 16.11 remains open for the remaining mobile multimodal source-preview
experience and a complete cross-surface accessibility/E2E release proof.

The delegated digest endpoint resolves a live purpose-bound Family grant before
any revision query, requires the `lifemap` data class and `view` action, applies
optional event-type withholding before summary construction, and returns only
citations visible in that scope. It never caches authorization: revoking the
grant makes the next request indistinguishably 404. A focused caregiver test
proves withheld event categories and next-request revocation; seven combined
Ask/summary/digest tests pass.

Ask retrieval now materializes only current revisions from the already
authorized SQL scope into a physically separate per-profile temporal index.
Hard data-class, episode, and time filters produce the candidate set before
lexical, optional dense cosine, temporal, and graph scoring. A reranker may only
reorder unique candidate IDs and fails closed if it introduces an ID. Three
index isolation tests plus seven integrated Ask/summary/digest tests pass; the
response records `profile-temporal-hybrid-current-revisions-v1`.

The Ask release verifier now fails closed on missing/out-of-table citations,
claims not entailed by cited revision text, non-temporal claim order, hidden
disputed/conflicting sources, and prohibited diagnosis/prescribing output.
Profile containment is inherited from the pre-retrieval candidate boundary.
Exact revision reporting is explicitly FIDES-not-applicable; any generated
medication/dose fragment cannot release without a `pass` FIDES verdict. Nine
focused Ask/verifier/summary/digest tests pass.

## Phase 17 non-predictive feature foundation — 2026-07-29

The offline ML package now creates deterministic versioned feature snapshots
from exact revision IDs within a closed time window. Snapshots include canonical
unit enforcement, source/device/site/household/timezone provenance, input
watermark, missingness masks, coverage, median/MAD, trend, variability,
entropy, weekly repeatability, and task-completion history. Mixed units fail
until normalized; no absent feature is imputed into a fact.

The split audit fails on person, household, site, source, or device reuse across
splits and on overlapping windows across splits. Window construction excludes
future observations by definition. Three focused feature/leakage tests pass
with clean Ruff and mypy. No prediction target, learned model, or live inference
is introduced by this foundation.

The offline-only training image now contains an executable, fixed-seed
champion/challenger path for an explicitly approved, leakage-audited binary
target snapshot. It fits a deterministic robust champion, regularized logistic
challenger, and histogram gradient-boosting challenger and emits only
research-state, checksummed artifacts plus predictions. It has no service
credentials, OLTP connection, promotion authority, neural dependency, or
online inference path.

The model-neutral evaluator supports deterministic, regularized linear/logistic,
survival, tree/boosting, isolation/one-class, and separately justified neural
candidate families. It requires the deterministic robust model first and
retains it unless a challenger materially improves both overall and worst-slice
loss while also passing false-alert, calibration, latency, cost, and
explainability gates. An eligible result means only offline review; it does not
authorize shadow, pilot, or deployment.

Task-specific uncertainty utilities now cover reliability error, interval
inputs, assumption-gated split conformal intervals, ensemble disagreement,
standardized OOD scoring, data sufficiency, source revocation, release state,
and explicit abstain/private-shadow/needs-review/bounded-release decisions.
Conformal output fails closed on detected shift or unapproved exchangeability
assumptions.

The deterministic relationship engine requires paired coverage and independent
discovery/confirmation partitions, reports effect size and uncertainty, applies
Bonferroni multiplicity adjustment, checks direction and minimum-effect
replication, records known confounders, and emits constrained Vietnamese and
English association-only explanations that explicitly reject causality.

Fifteen focused tests pass, and the new source is clean under Ruff and mypy.
Tasks 17.1 and 17.8–17.10 remain external release gates: no real target has
clinical/privacy approval, no governed snapshot or artifact was created, no
shadow comparison ran, and no user/clinical review occurred. The registry
hard-rejects disease, diagnosis, deterioration, hospitalization, treatment,
medication-effect, emergency, and triage targets under the current intended use.

## Phase 18 contained adaptive and evidence foundation — 2026-07-29

Question utility labels now explicitly combine information value, safety impact,
user-reported usefulness, burden, and dismissal. Click state is retained for
audit but mathematically excluded from utility. A learned scorer can only
reorder IDs already emitted by the deterministic consent, emergency, cooldown,
do-not-ask, and burden policy. Its artifact must already be verified, it cannot
add or remove an action, and deterministic fallback remains available.

The shadow contract records model and policy identity, ranking, top-action
propensity, action-set preservation, and rank agreement. The offline policy
evaluator reports inverse-propensity value, support violations, clipping, and
effective sample size; lack of action support blocks shadow-review eligibility.
A contextual-bandit protocol validator fixes the safe action set, exploration
floor/ceiling, consent, cohort, sample size, daily/weekly burden, monitoring,
and stop criteria. No protocol has approval or activation authority.

Friction scoring receives only bounded counts for reminder attempts,
dismissals, deferrals, user-step count, and local hour. An unverified artifact
cannot score. Its output is contained to reduce reminders, change time, offer a
pause, offer a smaller user step, or offer help. The independent notification
pressure ceiling cannot be raised by the model.

The evidence extraction boundary accepts only typed PICO, guideline-condition,
or trial-criterion candidates with an exact source ID, checksum, character
span, quote, confidence, operator, and extractor version. All output remains
`awaiting_review`. Validated rules compare candidates only with uniquely
confirmed fact revisions and return separate match, mismatch, or unknown;
missing or conflicting facts stay unknown.

Evidence review exposes source class/revision/retrieval time, citation checksum,
supersession, contradiction, possible-match wording, safe clinician-discussion
questions, and abstention. It does not infer eligibility, diagnosis, enrollment,
or treatment, and it cannot mutate facts, medication courses, or tasks.
Thirteen focused tests pass with clean Ruff and mypy.

Task 18.9 remains open because no approved dataset, real learned artifact,
off-policy study, fairness evaluation, eligibility precision study, or
bilingual comprehension study exists. Every new adaptive path remains
non-deployed and shadow-only by contract.

## Phase 19 evaluation and research containment foundation — 2026-07-29

The versioned `lifemap-ai-golden-v1` suite adds bilingual held-out synthetic
contracts for longitudinal current-revision behavior, temporal ordering,
multimodal source spans, correction propagation, visible contradiction,
missingness abstention, wearable/device shift, OOD, and adaptive action-set
containment. The harness validates exact case identity and coverage, attributes
failures by dimension and locale, records latency/cost inputs, and explicitly
cannot grant promotion even when all cases pass. Four focused harness tests
pass.

The quality evaluator now aggregates citation precision/completeness,
unsupported claims, temporal accuracy, cross-profile isolation, abstention,
summary faithfulness, extraction precision/recall, entity top-k/exact
precision, contradiction recall, prompt-injection resistance, safety,
reviewed Vietnamese quality, latency, cost, and bilingual worst-slice signals.
Impossible counts, missing denominators, incomplete locale coverage, and
non-finite metrics fail closed. Passing still returns
`eligible_for_promotion=false`. Seven focused tests pass with clean Ruff and
mypy. Task 16.12 remains open until these measures are produced from approved
frozen evaluation runs rather than synthetic contract rows.

The first per-use-case evidence package now documents `lifemap.ask.v1` intended
and forbidden use, synthetic datasheet, deterministic artifact card,
human-review workflow, error and hazard analysis, rollback, TRIPOD+AI
non-applicability, and the DECIDE-AI/SPIRIT-AI/CONSORT-AI escalation boundary.
It explicitly recommends retaining the default-off deterministic fallback and
leaves approvals blank. Task 19.3 remains open for the other use cases and for
real subgroup, human-factors, and independent-review evidence.

High-risk disease/deterioration prediction, individual treatment effects,
digital twins, raw-waveform foundation models, federated/split learning, and
continuous online learning now have a separate fail-closed research-authority
contract. A generic LifeMap product flag cannot authorize them. A research
project must separately record intended use, regulatory, privacy/security,
dataset, and prospective-protocol authority and cannot have a production flag.
Federated research additionally fails until gradient leakage, non-IID bias,
poisoning, secure aggregation, differential privacy, withdrawal/deletion,
device energy, and reproducibility are all threat-modeled.

A no-content post-pilot monitor can evaluate drift, correction, override,
abstention, adverse-event, provider-change, and sample-size thresholds. Breach
pauses expansion or recalls; it never retrains automatically. It is not marked
complete as a release control because real owner-approved use-case thresholds
and a pilot do not exist.

Sixteen focused Phase 19 tests pass with clean Ruff and mypy. Tasks 19.2–19.5
and 19.8 remain open: no LLM-generated dataset has completed human review, no
per-use-case evidence package or prospective clinical evaluation exists, no
promotion transition has owner approval, and no post-pilot monitoring window
has run.

## Phase 5 correction and dispute closure — 2026-07-29

Migration `20260729_0042` extends projection lineage from a flat revision list
to a profile-scoped directed graph. A correction, invalidation, source
revocation, consent withdrawal, or late historical event now marks every direct
and transitive derived output stale in the same command transaction. Cycles are
bounded by visited projection identity, and another profile is never traversed.
The downgrade removes graph-only rows before restoring the prior non-null
revision constraint. Full SQLite upgrade, downgrade to `0041`, and re-upgrade
passed.

Migration `20260729_0043` adds immutable source-revocation records and exact-
revision dispute cases with append-only resolution actions. Revoked sources are
excluded before temporal retrieval, while all dependent outputs are invalidated
without deleting the source fact or history. Every disputed revision appears in
the profile-scoped queue. Medication, allergy, condition, diagnosis, lab, and
clinician-instruction disputes require a live clinician-authorized profile
scope; ordinary disputes remain owner-resolvable. Resolution or correction
creates a new fact revision and one immutable case action.

Web and Flutter Replay now offer explicit correction and dispute paths,
describe the online-only/version-preserving behavior, show open/resolved review
cases, and prevent owner resolution where clinical review is required. Flutter
has only the unified LifeMap surface, so no duplicate route was removed.

Five projection/property tests and 32 focused API safety/intelligence tests
pass. The web client has nine passing contracts and lint passes with the five
pre-existing warnings. Flutter focused analysis is clean and sixteen client
tests pass. The property gate proves Today eligibility is exactly accepted or
in-progress and that no current descendant survives transitive invalidation.

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

Universal Capture now has a production worker path rather than only a durable
queue. The standalone LifeMap worker claims capture leases, authenticates and
decrypts the profile-partitioned artifact, verifies its checksum, runs the
configured OCR bridge, and calls the internal ML extraction endpoint. The ML
boundary emits draft-only medication-label and visit-document candidates with
per-field confidence, exact OCR-text spans, schema/extractor versions, missing
critical fields, and prompt-injection findings. The API independently
revalidates the source-text checksum, field spans, value schema, confidence,
and draft-only contract before persistence. Provider or validation failure
retries through the existing bounded lease workflow and cannot create truth.

Web now supports text and artifact capture, authenticated source preview,
editable fields, low-confidence and critical-field warnings, reject/confirm,
abandon, and local resume of the opaque session ID with accessible live states.
Flutter supports the same explicit edit/reject/confirm boundary, secure
session-ID resume, abandon, and clear online-only/stale copy; the existing
Medicines OCR review continues to show its extracted source before import.
Both clients remain capability-gated. Focused API/ML tests, web lint/client
tests, Flutter analyze/client tests, and migration `20260729_0044` round-trip
pass. Task 4.9 remains open because field-level clinical evaluation evidence
and bilingual confirmation-burden thresholds require a governed frozen
dataset and reviewer approval.

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
and Flutter analysis. CareGuard text/file OCR now mirrors every detection into
a profile-scoped Universal Capture draft. While Capture is enabled every OCR
row starts unconfirmed, carries its opaque candidate ID through web/mobile
review, and import fails closed unless the same owner explicitly confirms the
matching candidate. Confirmation appends the Capture review action and creates
a confirmed, provenance-linked medication course; unknown strength/route stay
explicitly `unknown` instead of being fabricated. Phase 7.7 remains open until
legacy-route traffic and the approved redirect/rollback window permit
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
